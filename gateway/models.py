import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Banner(models.Model):
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    # 📸 Image uploaded directly through Django Admin / File upload
    image = models.ImageField(upload_to='banners/', blank=True, null=True)
    # Optional fallback URL field
    image_url = models.URLField(blank=True, null=True)
    action_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def get_image_url(self):
        """Returns the uploaded image URL or fallback to image_url string."""
        if self.image:
            return self.image.url
        return self.image_url or ''

class GatewaySubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    api_key = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    is_active = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    trial_sms_remaining = models.IntegerField(default=10) # 🎁 10 Free Trial SMS

    def can_send_sms(self):
        if self.is_active and self.expires_at and self.expires_at > timezone.now():
            return True, "PAID"
        if self.trial_sms_remaining > 0:
            return True, "TRIAL"
        return False, "EXPIRED"

class SMSQueue(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sms_queue')
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=15, default='QUEUED')
    created_at = models.DateTimeField(auto_now_add=True)

class SubscriptionPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payment_reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)


class ContactGroup(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contact_groups')
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Contact(models.Model):
    group = models.ForeignKey(ContactGroup, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'phone_number')

    def __str__(self):
        return f"{self.name or 'No Name'} - {self.phone_number}"