import uuid
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.shortcuts import redirect
from django.db import transaction as db_transaction
from django.utils import timezone

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
        """Return Google OAuth URL in JSON response"""
        try:
            auth_url = GoogleAuthHelper.get_auth_url()
            return Response(
                ResponseHelper.success_response(
                    data={'google_auth_url': auth_url},
                    message="Google authentication URL generated"
                ),
                status=status.HTTP_200_OK
            )
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
            # Exchange code for token
            token_data = GoogleAuthHelper.exchange_code_for_token(code)
            if not token_data:
                logger.error("Failed to exchange code for token")
                return Response(
                    ResponseHelper.error_response(
                        message="Invalid or expired authorization code"
                    ),
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get user info
            user_info = GoogleAuthHelper.get_user_info(token_data['access_token'])
            if not user_info:
                logger.error("Failed to fetch user info from Google")
                return Response(
                    ResponseHelper.error_response(
                        message="Failed to retrieve user information"
                    ),
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create or update user
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
            
            serializer = UserSerializer(user)
            return Response(
                ResponseHelper.success_response(
                    data=serializer.data,
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
    
    def post(self, request):
        """Initiate Paystack payment"""
        serializer = PaymentInitiateSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.warning(f"Invalid payment initiation data: {serializer.errors}")
            return Response(
                ResponseHelper.error_response(
                    message="Invalid input data",
                    errors=serializer.errors
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data = serializer.validated_data
            user_id = data['user_id']
            amount = data['amount']
            
            # Check if user exists
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User not found: {user_id}")
                return Response(
                    ResponseHelper.error_response(
                        message="User not found"
                    ),
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check for duplicate transaction (idempotency)
            # Generate a reference using user_id and timestamp
            reference = f"TXN_{user_id}_{int(timezone.now().timestamp())}"
            
            existing_transaction = Transaction.objects.filter(
                reference=reference,
                user=user,
                amount=amount
            ).first()
            
            if existing_transaction:
                logger.info(f"Duplicate transaction detected, returning existing: {reference}")
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
            
            # Initialize Paystack transaction
            paystack_response = PaystackHelper.initialize_transaction(
                amount=amount,
                email=user.email,
                reference=reference,
                metadata={
                    'user_id': str(user_id),
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
            
            # Save transaction
            transaction = Transaction.objects.create(
                reference=reference,
                user=user,
                amount=amount / 100,  # Convert from Kobo to Naira
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
                        'authorization_url': transaction.authorization_url,
                        'amount': amount,
                        'currency': 'NGN'
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
        # Get signature from header
        signature = request.headers.get('x-paystack-signature')
        
        if not signature:
            logger.warning("Webhook received without signature")
            return Response(
                ResponseHelper.error_response(message="Missing signature"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate signature
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
                
                # Find transaction
                try:
                    transaction = Transaction.objects.get(paystack_reference=reference)
                    
                    # Update transaction
                    transaction.status = 'success'
                    transaction.paid_at = timezone.now()
                    transaction.metadata['webhook_data'] = data
                    transaction.save()
                    
                    logger.info(f"Transaction {reference} marked as successful")
                    
                except Transaction.DoesNotExist:
                    logger.warning(f"Transaction not found for webhook reference: {reference}")
                    # Optionally create a new transaction record
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
                ResponseHelper.success_response(message="Webhook processed"),
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
    
    def get(self, request, reference):
        """Check transaction status"""
        refresh = request.GET.get('refresh', 'false').lower() == 'true'
        
        try:
            # Find transaction
            transaction = Transaction.objects.get(reference=reference)
            
            if refresh or transaction.status == 'pending':
                # Verify with Paystack
                paystack_data = PaystackHelper.verify_transaction(
                    transaction.paystack_reference or transaction.reference
                )
                
                if paystack_data:
                    # Update transaction based on Paystack response
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
            
            serializer = TransactionSerializer(transaction)
            return Response(
                ResponseHelper.success_response(
                    data=serializer.data,
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