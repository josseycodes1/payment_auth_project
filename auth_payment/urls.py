from django.urls import path
from .views import (
    GoogleAuthInitiateView,
    GoogleAuthCallbackView,
    PaystackInitiatePaymentView,
    PaystackWebhookView,
    TransactionStatusView,
    TransactionListView,
)

urlpatterns = [
    # Google OAuth endpoints
    path('auth/google', GoogleAuthInitiateView.as_view(), name='google-auth-initiate'),
    path('auth/google/callback', GoogleAuthCallbackView.as_view(), name='google-auth-callback'),
    
    # Paystack payment endpoints
    path('payments/paystack/initiate', PaystackInitiatePaymentView.as_view(), name='paystack-initiate'),
    path('payments/paystack/webhook', PaystackWebhookView.as_view(), name='paystack-webhook'),
    
    # Transaction endpoints
    path('payments/<str:reference>/status', TransactionStatusView.as_view(), name='transaction-status'),
    path('payments', TransactionListView.as_view(), name='transaction-list'),
]