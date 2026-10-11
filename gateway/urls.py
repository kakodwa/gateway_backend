# gateway/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('banners/', views.get_banners, name='get_banners'),

    # In-App Account Authentication
    path('app-register/', views.app_register_user, name='app_register'),
    path('app-login/', views.app_login_fetch_key, name='app_login'),

    # External Queueing & Gateway Hardware Endpoints
    path('send-sms/', views.send_sms_api, name='send_sms_api'),
    path('get-pending-sms/', views.get_pending_sms, name='get_pending_sms'),
    path('mark-sms-sent/', views.mark_sms_sent, name='mark_sms_sent'),
    path('check-subscription/', views.check_subscription_status, name='check_subscription'),

    # Contact & Bulk Endpoints
    path('contact-groups/', views.contact_groups_api, name='contact_groups'),
    path('contact-groups/<int:group_id>/', views.contact_groups_api, name='delete_contact_group'),
    path('contact-groups/<int:group_id>/contacts/', views.contacts_api, name='contacts_api'),
    path('contact-groups/<int:group_id>/contacts/<int:contact_id>/', views.contacts_api, name='delete_contact'),
    path('send-bulk-sms/', views.send_bulk_sms_api, name='send_bulk_sms'),

    # Monetization / PayChangu
    path('payments/initiate/', views.initiate_subscription_payment, name='initiate_payment'),
    path('payments/status/<str:reference>/', views.verify_payment_status, name='verify_payment'),
]