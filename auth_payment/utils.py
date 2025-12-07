import requests
import hashlib
import hmac
import json
import logging
from django.conf import settings
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class GoogleAuthHelper:
    @staticmethod
    def get_auth_url():
        """Generate Google OAuth URL"""
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        
        if not redirect_uri and hasattr(settings, 'BASE_URL'):
            base_url = settings.BASE_URL
            redirect_uri = f"{base_url}/api/v1/auth/google/callback"
        
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent',
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        logger.info(f"Generated Google auth URL with redirect_uri: {redirect_uri}")
        return auth_url

    @staticmethod
    def exchange_code_for_token(code):
        """Exchange authorization code for access token"""
        token_url = 'https://oauth2.googleapis.com/token'
        
        # Get redirect URI from settings
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        if not redirect_uri and hasattr(settings, 'BASE_URL'):
            base_url = settings.BASE_URL
            redirect_uri = f"{base_url}/api/v1/auth/google/callback"
        
        data = {
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }
        
        logger.info(f"Exchanging code for token with redirect_uri: {redirect_uri}")
        response = requests.post(token_url, data=data)
        
        if response.status_code != 200:
            logger.error(f"Google token exchange failed: {response.status_code} - {response.text}")
            return None
        
        return response.json()


class PaystackHelper:
    BASE_URL = 'https://api.paystack.co'
    
    @staticmethod
    def get_headers():
        return {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }
    
    @staticmethod
    def initialize_transaction(amount, email, reference=None, metadata=None):
        """Initialize Paystack transaction"""
        url = f"{PaystackHelper.BASE_URL}/transaction/initialize"
        data = {
            'amount': amount,
            'email': email,
            'reference': reference,
            'metadata': metadata or {},
            'callback_url': f"{settings.BASE_URL}/payments/callback",  # Update with your actual callback URL
        }
        
        logger.info(f"Initializing Paystack transaction for {email}, amount: {amount}")
        
        try:
            response = requests.post(url, json=data, headers=PaystackHelper.get_headers())
            response.raise_for_status()
            result = response.json()
            
            if result['status']:
                logger.info(f"Paystack transaction initialized successfully: {result['data']['reference']}")
                return result['data']
            else:
                logger.error(f"Paystack initialization failed: {result.get('message', 'Unknown error')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack API error: {str(e)}")
            return None
    
    @staticmethod
    def verify_transaction(reference):
        """Verify transaction status with Paystack"""
        url = f"{PaystackHelper.BASE_URL}/transaction/verify/{reference}"
        
        logger.info(f"Verifying Paystack transaction: {reference}")
        
        try:
            response = requests.get(url, headers=PaystackHelper.get_headers())
            response.raise_for_status()
            result = response.json()
            
            if result['status']:
                logger.info(f"Transaction {reference} verified: {result['data']['status']}")
                return result['data']
            else:
                logger.error(f"Transaction verification failed: {result.get('message', 'Unknown error')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack verification API error: {str(e)}")
            return None
    
    @staticmethod
    def validate_webhook_signature(payload, signature):
        """Validate Paystack webhook signature"""
        computed_signature = hmac.new(
            settings.PAYSTACK_WEBHOOK_SECRET.encode('utf-8'),
            json.dumps(payload, separators=(',', ':')).encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        is_valid = hmac.compare_digest(computed_signature, signature)
        
        if not is_valid:
            logger.warning("Invalid webhook signature detected")
        
        return is_valid


class ResponseHelper:
    @staticmethod
    def success_response(data=None, message="Success", status_code=200):
        response = {
            'success': True,
            'message': message,
            'data': data or {}
        }
        logger.info(f"Success response: {message}")
        return response
    
    @staticmethod
    def error_response(message="Error", errors=None, status_code=400):
        response = {
            'success': False,
            'message': message,
            'errors': errors or {}
        }
        logger.error(f"Error response ({status_code}): {message}")
        return response