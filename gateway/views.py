import json
import uuid
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import GatewaySubscription, SMSQueue, SubscriptionPayment, Banner, ContactGroup, Contact
from .paychangu_service import PayChanguService



paychangu = PayChanguService()


def get_banners(request):
    """
    Returns active sliding banners for mobile display.
    """
    banners = Banner.objects.filter(is_active=True).order_by('-created_at')
    data = []
    
    for b in banners:
        img_path = b.get_image_url
        # Convert relative media path (/media/banners/pic.jpg) into full absolute URL
        full_image_url = request.build_absolute_uri(img_path) if img_path else None

        data.append({
            'id': b.id,
            'title': b.title,
            'description': b.description,
            'image_url': full_image_url,
            'action_url': b.action_url,
        })

    return JsonResponse({'banners': data}, safe=False)


@csrf_exempt
def app_register_user(request):
    """
    Manual Registration Endpoint:
    Registers a new Django User, generates a GatewaySubscription with 10 Free Trial SMS,
    and returns their unique X-Api-Key.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return JsonResponse({'error': 'Username and password are required'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username is already taken'}, status=400)

        # 1. Create Django User
        user = User.objects.create_user(username=username, email=email, password=password)

        # 2. Assign Gateway Subscription with 10 Free Trial SMS
        sub = GatewaySubscription.objects.create(
            user=user,
            api_key=f"gw_{uuid.uuid4().hex}",
            is_active=False,
            trial_sms_remaining=10
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Account registered successfully!',
            'api_key': sub.api_key,
            'trial_remaining': sub.trial_sms_remaining
        }, status=201)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def app_login_fetch_key(request):
    """
    Manual Login Endpoint:
    Authenticates user credentials and fetches their assigned X-Api-Key from the database.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        user = authenticate(username=username, password=password)
        if user is None:
            return JsonResponse({'error': 'Invalid username or password'}, status=401)

        sub, created = GatewaySubscription.objects.get_or_create(user=user)

        return JsonResponse({
            'status': 'success',
            'message': 'Login successful!',
            'api_key': sub.api_key,
            'is_active': sub.is_active,
            'trial_remaining': sub.trial_sms_remaining
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def send_sms_api(request):
    """
    📩 External System Endpoint:
    Allows user apps/algorithms to queue SMS via POST request.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    api_key = request.headers.get('X-Api-Key')
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
        can_send, _ = sub.can_send_sms()
        
        if not can_send:
            return JsonResponse({
                'error': 'Free trial limit reached or subscription expired.',
                'code': 'SUBSCRIPTION_EXPIRED'
            }, status=402)
            
    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized - Invalid X-Api-Key'}, status=401)

    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        message = data.get('message')

        if not phone_number or not message:
            return JsonResponse({'error': 'phone_number and message are required'}, status=400)

        sms_item = SMSQueue.objects.create(
            user=sub.user,
            phone_number=phone_number,
            message=message,
            status='QUEUED'
        )

        return JsonResponse({
            'status': 'success',
            'message': 'SMS queued successfully',
            'sms_id': sms_item.id
        }, status=201)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def get_pending_sms(request):
    api_key = request.headers.get('X-Api-Key')
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
        can_send, plan_type = sub.can_send_sms()

        if not can_send:
            return JsonResponse({
                'error': 'Trial limit reached or subscription expired.',
                'code': 'SUBSCRIPTION_EXPIRED',
                'trial_remaining': sub.trial_sms_remaining
            }, status=402)

    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized - Invalid API Key'}, status=401)

    limit = 10
    if plan_type == "TRIAL":
        limit = min(10, sub.trial_sms_remaining)

    pending = SMSQueue.objects.filter(user=sub.user, status='QUEUED')[:limit]
    data = [{'id': m.id, 'phone_number': m.phone_number, 'message': m.message} for m in pending]
    
    SMSQueue.objects.filter(id__in=[m['id'] for m in data]).update(status='PROCESSING')
    return JsonResponse(data, safe=False)


@csrf_exempt
def mark_sms_sent(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    api_key = request.headers.get('X-Api-Key')
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    data = json.loads(request.body)
    sms_id = data.get('sms_id')
    status = data.get('status', 'SENT')

    updated = SMSQueue.objects.filter(id=sms_id, user=sub.user).update(status=status)

    if updated and status == 'SENT' and sub.trial_sms_remaining > 0 and not sub.is_active:
        sub.trial_sms_remaining -= 1
        sub.save()

    return JsonResponse({
        'status': 'success',
        'trial_remaining': sub.trial_sms_remaining
    })


@csrf_exempt
def initiate_subscription_payment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    data = json.loads(request.body)
    api_key = request.headers.get('X-Api-Key')
    
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Invalid API Key'}, status=401)

    payment_method = data.get('payment_method')
    phone_number = data.get('phone_number', '')
    amount = 15000.00  # Default Monthly Subscription Fee (MWK)

    payment_ref = f"SUB-{sub.user.id}-{int(timezone.now().timestamp())}"

    payment = SubscriptionPayment.objects.create(
        user=sub.user,
        payment_reference=payment_ref,
        amount=amount,
        payment_method=payment_method,
        status='pending'
    )

    if payment_method in ['airtel_money', 'tnm_mpamba']:
        result = paychangu.initiate_mobile_money(payment, phone_number)
        if result.get('success'):
            return JsonResponse({
                'status': 'initiated',
                'payment_reference': payment_ref,
                'message': 'PIN prompt sent to phone'
            })
        return JsonResponse({'error': result.get('error')}, status=400)

    elif payment_method == 'visa_card':
        redirect_url = f"https://yourdomain.com/api/payments/return/?ref={payment_ref}"
        result = paychangu.initiate_card_payment(payment, redirect_url=redirect_url)
        if result.get('success'):
            checkout_url = result['data']['data']['checkout_url']
            return JsonResponse({
                'status': 'initiated',
                'payment_reference': payment_ref,
                'checkout_url': checkout_url
            })
        return JsonResponse({'error': result.get('error')}, status=400)

    return JsonResponse({'error': 'Invalid payment method'}, status=400)


def verify_payment_status(request, reference):
    try:
        payment = SubscriptionPayment.objects.get(payment_reference=reference)
        if payment.status == 'completed':
            return JsonResponse({'status': 'completed'})

        res = paychangu.verify_payment(reference)
        if res.get('success') and res['data'].get('status') == 'success':
            payment.status = 'completed'
            payment.save()

            sub = GatewaySubscription.objects.get(user=payment.user)
            now = timezone.now()
            start_time = sub.expires_at if (sub.expires_at and sub.expires_at > now) else now
            sub.expires_at = start_time + timedelta(days=30)
            sub.is_active = True
            sub.save()

            return JsonResponse({'status': 'completed'})

        return JsonResponse({'status': payment.status})
    except SubscriptionPayment.DoesNotExist:
        return JsonResponse({'error': 'Payment reference not found'}, status=404)


def check_subscription_status(request):
    api_key = request.headers.get('X-Api-Key')
    if not api_key:
        return JsonResponse({'error': 'X-Api-Key header missing'}, status=400)

    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
        can_send, plan_type = sub.can_send_sms()
        
        return JsonResponse({
            'can_send': can_send,
            'plan_type': plan_type,
            'is_active': sub.is_active,
            'trial_sms_remaining': sub.trial_sms_remaining,
            'expires_at': sub.expires_at.isoformat() if sub.expires_at else None
        })
    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Invalid API Key'}, status=404)


@csrf_exempt
def contact_groups_api(request, group_id=None):
    """GET to list, POST to create, DELETE to remove a group."""
    api_key = request.headers.get('X-Api-Key')
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    if request.method == 'GET':
        groups = ContactGroup.objects.filter(user=sub.user).order_by('-created_at')
        data = [{
            'id': g.id,
            'name': g.name,
            'description': g.description,
            'contact_count': g.contacts.count()
        } for g in groups]
        return JsonResponse({'groups': data})

    elif request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return JsonResponse({'error': 'Group name is required'}, status=400)

        group = ContactGroup.objects.create(user=sub.user, name=name, description=description)
        return JsonResponse({'status': 'success', 'group_id': group.id, 'name': group.name}, status=201)

    elif request.method == 'DELETE':
        if not group_id:
            return JsonResponse({'error': 'Group ID required'}, status=400)
        
        deleted_count, _ = ContactGroup.objects.filter(id=group_id, user=sub.user).delete()
        if deleted_count > 0:
            return JsonResponse({'status': 'success', 'message': 'Group deleted successfully'})
        return JsonResponse({'error': 'Group not found or unauthorized'}, status=404)


@csrf_exempt
def contacts_api(request, group_id, contact_id=None):
    """GET list, POST add, DELETE remove a specific contact."""
    api_key = request.headers.get('X-Api-Key')
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
        group = ContactGroup.objects.get(id=group_id, user=sub.user)
    except (GatewaySubscription.DoesNotExist, ContactGroup.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized or group not found'}, status=404)

    if request.method == 'GET':
        contacts = Contact.objects.filter(group=group).order_by('-created_at')
        data = [{'id': c.id, 'name': c.name, 'phone_number': c.phone_number} for c in contacts]
        return JsonResponse({'contacts': data})

    elif request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        phone_number = data.get('phone_number', '').strip()

        if not phone_number:
            return JsonResponse({'error': 'Phone number is required'}, status=400)

        contact, created = Contact.objects.get_or_create(
            group=group,
            phone_number=phone_number,
            defaults={'name': name}
        )
        return JsonResponse({'status': 'success', 'contact_id': contact.id}, status=201)

    elif request.method == 'DELETE':
        if not contact_id:
            return JsonResponse({'error': 'Contact ID required'}, status=400)

        deleted_count, _ = Contact.objects.filter(id=contact_id, group=group).delete()
        if deleted_count > 0:
            return JsonResponse({'status': 'success', 'message': 'Contact deleted successfully'})
        return JsonResponse({'error': 'Contact not found'}, status=404)

@csrf_exempt
def send_bulk_sms_api(request):
    """OFFLOADED BULK QUEUEING: Bulk queues SMS entries without freezing mobile UI."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    api_key = request.headers.get('X-Api-Key')
    try:
        sub = GatewaySubscription.objects.get(api_key=api_key)
        can_send, _ = sub.can_send_sms()
        if not can_send:
            return JsonResponse({'error': 'Subscription expired or trial limit reached'}, status=402)
    except GatewaySubscription.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        message = data.get('message', '').strip()

        if not group_id or not message:
            return JsonResponse({'error': 'group_id and message are required'}, status=400)

        group = ContactGroup.objects.get(id=group_id, user=sub.user)
        contacts = Contact.objects.filter(group=group)

        if not contacts.exists():
            return JsonResponse({'error': 'Selected group has no contacts'}, status=400)

        # Single bulk insertion to eliminate database roundtrips
        queue_objects = [
            SMSQueue(user=sub.user, phone_number=c.phone_number, message=message, status='QUEUED')
            for c in contacts
        ]
        SMSQueue.objects.bulk_create(queue_objects)

        return JsonResponse({
            'status': 'success',
            'message': f'Queued {len(queue_objects)} SMS messages for group "{group.name}"',
            'queued_count': len(queue_objects)
        }, status=201)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)