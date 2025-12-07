from django.contrib import admin
from .models import User, Transaction

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('email', 'name', 'google_id')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'amount', 'status', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference', 'user__email', 'paystack_reference')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user',)