import uuid
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.shortcuts import redirect
from django.db import transaction as db_transaction
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import timedelta

from .models import User, Transaction
from .serializers import (
    UserSerializer, PaymentInitiateSerializer, 
    TransactionStatusSerializer, TransactionSerializer
)
from .utils import GoogleAuthHelper, PaystackHelper, ResponseHelper

logger = logging.getLogger(__name__)


class GoogleAuthInitiateView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Return Google OAuth URL in JSON response OR redirect"""
        try:
            auth_url = GoogleAuthHelper.get_auth_url()
            
            
            accept_header = request.headers.get('Accept', '')
            
            if 'application/json' in accept_header or request.GET.get('format') == 'json':
               
                return Response(
                    ResponseHelper.success_response(
                        data={'google_auth_url': auth_url},
                        message="Google authentication URL generated"
                    ),
                    status=status.HTTP_200_OK
                )
            else:
                
                return redirect(auth_url)
                
        except Exception as e:
            logger.error(f"Error generating Google auth URL: {str(e)}")
            return Response(
                ResponseHelper.error_response(
                    message="Failed to generate authentication URL",
                    errors={'detail': str(e)}
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GoogleAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Handle Google OAuth callback"""
        code = request.GET.get('code')
        error = request.GET.get('error')
        
        if error:
            logger.error(f"Google OAuth error: {error}")
            return Response(
                ResponseHelper.error_response(
                    message=f"Authentication failed: {error}"
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not code:
            logger.error("No authorization code provided")
            return Response(
                ResponseHelper.error_response(
                    message="Authorization code is required"
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
           
            token_data = GoogleAuthHelper.exchange_code_for_token(code)
            if not token_data:
                logger.error("Failed to exchange code for token")
                return Response(
                    ResponseHelper.error_response(
                        message="Invalid or expired authorization code"
                    ),
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            
            user_info = GoogleAuthHelper.get_user_info(token_data['access_token'])
            if not user_info:
                logger.error("Failed to fetch user info from Google")
                return Response(
                    ResponseHelper.error_response(
                        message="Failed to retrieve user information"
                    ),
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            
            with db_transaction.atomic():
                user, created = User.objects.update_or_create(
                    google_id=user_info.get('sub'),
                    defaults={
                        'email': user_info.get('email'),
                        'name': user_info.get('name'),
                        'picture': user_info.get('picture'),
                    }
                )
            
            action = "created" if created else "updated"
            logger.info(f"User {action}: {user.email}")
            
            
            return Response(
                ResponseHelper.success_response(
                    data={
                        'user_id': str(user.id),
                        'email': user.email,
                        'name': user.name
                    },
                    message=f"User authentication successful"
                ),
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Google authentication error: {str(e)}")
            return Response(
                ResponseHelper.error_response(
                    message="Authentication failed",
                    errors={'detail': str(e)}
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaystackInitiatePaymentView(APIView):
    
    @swagger_auto_schema(
        operation_description="Initiate Paystack payment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['amount'],
            properties={
                'amount': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Amount in Kobo (minimum 100 Kobo = 1 NGN)',
                    minimum=100,
                    example=5000
                )
            }
        ),
        responses={
            201: openapi.Response(
                description='Payment initialized successfully',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'reference': openapi.Schema(type=openapi.TYPE_STRING),
                                'authorization_url': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description='Invalid input'),
            402: openapi.Response(description='Payment initialization failed by Paystack'),
            500: openapi.Response(description='Internal server error')
        }
    )
    def post(self, request):
        """Initiate Paystack payment"""
        
        serializer = PaymentInitiateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                ResponseHelper.error_response(
                    message="Invalid input",
                    errors=serializer.errors
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = serializer.validated_data['amount']
        
        try:
            
            user = None
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            
            if not user:
                try:
                    user = User.objects.first()
                    if not user:
                        return Response(
                            ResponseHelper.error_response(
                                message="No users found. Please authenticate first via Google OAuth."
                            ),
                            status=status.HTTP_401_UNAUTHORIZED
                        )
                except User.DoesNotExist:
                    return Response(
                        ResponseHelper.error_response(
                            message="User authentication required. Please authenticate first via Google OAuth."
                        ),
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            
            
            reference = f"TXN_{user.id}_{int(timezone.now().timestamp())}"
            
            time_threshold = timezone.now() - timedelta(minutes=5)
            existing_transaction = Transaction.objects.filter(
                user=user,
                amount=amount / 100,
                status='pending',
                created_at__gte=time_threshold
            ).order_by('-created_at').first()

            if existing_transaction:
                logger.info(f"Duplicate transaction detected, returning existing: {existing_transaction.reference}")
                return Response(
                    ResponseHelper.success_response(
                        data={
                            'reference': existing_transaction.reference,
                            'authorization_url': existing_transaction.authorization_url
                        },
                        message="Transaction already initiated"
                    ),
                    status=status.HTTP_200_OK
                )
            
            
            paystack_response = PaystackHelper.initialize_transaction(
                amount=amount,
                email=user.email,
                reference=reference,
                metadata={
                    'user_id': str(user.id),
                    'user_name': user.name
                }
            )
            
            if not paystack_response:
                logger.error(f"Paystack initialization failed for user: {user.email}")
                return Response(
                    ResponseHelper.error_response(
                        message="Payment initialization failed"
                    ),
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )
            
            
            transaction = Transaction.objects.create(
                reference=reference,
                user=user,
                amount=amount / 100,  
                paystack_reference=paystack_response.get('reference'),
                authorization_url=paystack_response.get('authorization_url'),
                status='pending',
                metadata={
                    'paystack_response': paystack_response,
                    'user_data': {
                        'email': user.email,
                        'name': user.name
                    }
                }
            )
            
            logger.info(f"Payment initiated successfully: {reference}")
            
            
            return Response(
                ResponseHelper.success_response(
                    data={
                        'reference': transaction.reference,
                        'authorization_url': transaction.authorization_url
                    },
                    message="Payment initialized successfully"
                ),
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return Response(
                ResponseHelper.error_response(
                    message="Payment initiation failed",
                    errors={'detail': str(e)}
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Handle Paystack webhook notifications"""
        
        signature = request.headers.get('x-paystack-signature')
        
        if not signature:
            logger.warning("Webhook received without signature")
            return Response(
                ResponseHelper.error_response(message="Missing signature"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        if not PaystackHelper.validate_webhook_signature(request.data, signature):
            logger.warning("Invalid webhook signature")
            return Response(
                ResponseHelper.error_response(message="Invalid signature"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            event = request.data.get('event')
            data = request.data.get('data', {})
            
            logger.info(f"Webhook received: {event}")
            
            if event == 'charge.success':
                reference = data.get('reference')
                
                
                try:
                    transaction = Transaction.objects.get(paystack_reference=reference)
                    
                    
                    transaction.status = 'success'
                    transaction.paid_at = timezone.now()
                    transaction.metadata['webhook_data'] = data
                    transaction.save()
                    
                    logger.info(f"Transaction {reference} marked as successful")
                    
                except Transaction.DoesNotExist:
                    logger.warning(f"Transaction not found for webhook reference: {reference}")
                    
                    pass
                    
            elif event in ['charge.failed', 'charge.abandoned']:
                reference = data.get('reference')
                
                try:
                    transaction = Transaction.objects.get(paystack_reference=reference)
                    transaction.status = 'failed' if event == 'charge.failed' else 'abandoned'
                    transaction.metadata['webhook_data'] = data
                    transaction.save()
                    
                    logger.info(f"Transaction {reference} marked as {transaction.status}")
                    
                except Transaction.DoesNotExist:
                    logger.warning(f"Transaction not found for failed webhook: {reference}")
            
            return Response(
                {"status": True}, 
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return Response(
                ResponseHelper.error_response(
                    message="Webhook processing failed",
                    errors={'detail': str(e)}
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TransactionStatusView(APIView):
    
    @swagger_auto_schema(
        operation_description="Check transaction status",
        manual_parameters=[
            openapi.Parameter(
                'reference',
                openapi.IN_PATH,
                description="Transaction reference",
                type=openapi.TYPE_STRING,
                required=True,
                example="TXN_68c4808d-a9a1-4708-b8a2-cbfa7911c0e3_1733650123"
            ),
            openapi.Parameter(
                'refresh',
                openapi.IN_QUERY,
                description="Force refresh from Paystack (true/false)",
                type=openapi.TYPE_BOOLEAN,
                required=False,
                default=False
            )
        ],
        responses={
            200: openapi.Response(
                description='Transaction status retrieved',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'reference': openapi.Schema(type=openapi.TYPE_STRING),
                                'status': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    enum=['pending', 'success', 'failed', 'abandoned']
                                ),
                                'amount': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'paid_at': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format='date-time',
                                    nullable=True
                                )
                            }
                        )
                    }
                )
            ),
            404: openapi.Response(description='Transaction not found'),
            500: openapi.Response(description='Internal server error')
        }
    )
    def get(self, request, reference):
        """Check transaction status"""
        refresh = request.GET.get('refresh', 'false').lower() == 'true'
        
        try:
           
            transaction = Transaction.objects.get(reference=reference)
            
            if refresh or transaction.status == 'pending':
               
                paystack_data = PaystackHelper.verify_transaction(
                    transaction.paystack_reference or transaction.reference
                )
                
                if paystack_data:
                   
                    paystack_status = paystack_data.get('status')
                    
                    if paystack_status == 'success' and transaction.status != 'success':
                        transaction.status = 'success'
                        transaction.paid_at = timezone.now()
                        transaction.metadata['verified_at'] = timezone.now().isoformat()
                        transaction.save()
                        logger.info(f"Transaction {reference} verified as successful")
                    
                    elif paystack_status in ['failed', 'abandoned'] and transaction.status not in ['failed', 'abandoned']:
                        transaction.status = 'failed' if paystack_status == 'failed' else 'abandoned'
                        transaction.save()
                        logger.info(f"Transaction {reference} verified as {transaction.status}")
            
            
            return Response(
                ResponseHelper.success_response(
                    data={
                        'reference': transaction.reference,
                        'status': transaction.status,
                        'amount': int(transaction.amount * 100), 
                        'paid_at': transaction.paid_at.isoformat() if transaction.paid_at else None
                    },
                    message="Transaction status retrieved"
                ),
                status=status.HTTP_200_OK
            )
            
        except Transaction.DoesNotExist:
            logger.warning(f"Transaction not found: {reference}")
            return Response(
                ResponseHelper.error_response(
                    message="Transaction not found"
                ),
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Transaction status check error: {str(e)}")
            return Response(
                ResponseHelper.error_response(
                    message="Failed to retrieve transaction status",
                    errors={'detail': str(e)}
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TransactionListView(APIView):
    """List transactions for a user (bonus endpoint)"""
    
    @swagger_auto_schema(
        operation_description="List transactions for a user",
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_QUERY,
                description="User ID",
                type=openapi.TYPE_STRING,
                required=True,
                example="68c4808d-a9a1-4708-b8a2-cbfa7911c0e3"
            )
        ],
        responses={
            200: openapi.Response(description='Transactions retrieved successfully'),
            400: openapi.Response(description='user_id is required'),
            500: openapi.Response(description='Internal server error')
        }
    )
    def get(self, request):
        user_id = request.GET.get('user_id')
        
        if not user_id:
            return Response(
                ResponseHelper.error_response(message="user_id is required"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            transactions = Transaction.objects.filter(user_id=user_id).order_by('-created_at')
            serializer = TransactionSerializer(transactions, many=True)
            
            return Response(
                ResponseHelper.success_response(
                    data={'transactions': serializer.data},
                    message="Transactions retrieved successfully"
                ),
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error listing transactions: {str(e)}")
            return Response(
                ResponseHelper.error_response(
                    message="Failed to retrieve transactions"
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )