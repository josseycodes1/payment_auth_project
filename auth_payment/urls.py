from django.urls import path
from .views import (
    GoogleAuthInitiateView,
    GoogleAuthCallbackView,
    PaystackInitiatePaymentView,
    PaystackWebhookView,
    TransactionStatusView,
)

urlpatterns = [
    # Google OAuth endpoints (SPECIFICATION: /auth/google and /auth/google/callback)
    path('auth/google', GoogleAuthInitiateView.as_view(), name='google-auth-initiate'),
    path('auth/google/callback', GoogleAuthCallbackView.as_view(), name='google-auth-callback'),
    
    # Paystack payment endpoints (SPECIFICATION: /payments/paystack/initiate and /payments/paystack/webhook)
    path('payments/paystack/initiate', PaystackInitiatePaymentView.as_view(), name='paystack-initiate'),
    path('payments/paystack/webhook', PaystackWebhookView.as_view(), name='paystack-webhook'),
    
    # Transaction status endpoint (SPECIFICATION: /payments/{reference}/status)
    path('payments/<str:reference>/status', TransactionStatusView.as_view(), name='transaction-status'),
]