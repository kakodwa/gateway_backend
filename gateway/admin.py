# gateway/admin.py
from django.contrib import admin
from .models import GatewaySubscription, SMSQueue, SubscriptionPayment,Banner



@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')

@admin.register(GatewaySubscription)
class GatewaySubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 
        'api_key', 
        'is_active', 
        'trial_sms_remaining', 
        'expires_at', 
        'get_status_display'
    )
    list_filter = ('is_active', 'expires_at')
    search_fields = ('user__username', 'user__email', 'api_key')
    readonly_fields = ('api_key',)
    ordering = ('-id',)

    @admin.display(description='Current Plan Status')
    def get_status_display(self, obj):
        can_send, plan_type = obj.can_send_sms()
        if plan_type == "PAID":
            return "🟢 PAID ACTIVE"
        elif plan_type == "TRIAL":
            return f"🟠 TRIAL ({obj.trial_sms_remaining} left)"
        return "🔴 EXPIRED"


@admin.register(SMSQueue)
class SMSQueueAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'user', 
        'phone_number', 
        'message_preview', 
        'status', 
        'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('phone_number', 'message', 'user__username')
    ordering = ('-created_at',)

    @admin.display(description='Message')
    def message_preview(self, obj):
        return obj.message[:40] + "..." if len(obj.message) > 40 else obj.message


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_reference', 
        'user', 
        'amount', 
        'payment_method', 
        'status', 
        'created_at'
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('payment_reference', 'user__username', 'user__email')
    readonly_fields = ('payment_reference', 'created_at')
    ordering = ('-created_at',)