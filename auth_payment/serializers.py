from rest_framework import serializers
from .models import User, Transaction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'picture', 'created_at']
        read_only_fields = ['id', 'created_at']

class TransactionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'reference', 'user', 'user_id', 'amount', 'status',
            'authorization_url', 'paid_at', 'currency', 'created_at'
        ]
        read_only_fields = [
            'id', 'reference', 'status', 'authorization_url',
            'paid_at', 'created_at', 'updated_at'
        ]

class PaymentInitiateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=100)  # Minimum 100 Kobo (1 NGN)
    user_id = serializers.UUIDField()
    
    def validate_amount(self, value):
        if value < 100:
            raise serializers.ValidationError("Amount must be at least 100 Kobo (1 NGN)")
        return value

class TransactionStatusSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    status = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    paid_at = serializers.DateTimeField(allow_null=True)
    authorization_url = serializers.URLField(allow_null=True)