from django.urls import path
from .views import (
    GoogleAuthInitiateView,
    GoogleAuthCallbackView,
    PaystackInitiatePaymentView,
    PaystackWebhookView,
    TransactionStatusView,
)

urlpatterns = [
    
    path('auth/google', GoogleAuthInitiateView.as_view(), name='google-auth-initiate'),
    path('auth/google/callback', GoogleAuthCallbackView.as_view(), name='google-auth-callback'),
    
   
    path('payments/paystack/initiate', PaystackInitiatePaymentView.as_view(), name='paystack-initiate'),
    path('payments/paystack/webhook', PaystackWebhookView.as_view(), name='paystack-webhook'),
    
    
    path('payments/<str:reference>/status', TransactionStatusView.as_view(), name='transaction-status'),
]