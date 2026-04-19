import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils import timezone
from .models import Organization, Subscription
from .paddle_utils import (
    get_paddle_client, get_price_id,
    verify_webhook_signature, get_plan_from_price_id
)


# ─────────────────────────────────────────
# PRICING PAGE
# ─────────────────────────────────────────

def pricing(request):
    """Public pricing page with Paddle checkout buttons."""
    from .views import get_org
    org          = get_org(request) if request.user.is_authenticated else None
    subscription = getattr(org, 'subscription', None) if org else None

    return render(request, 'planner/pricing.html', {
        'prices':       settings.PADDLE_PRICES,
        'environment':  settings.PADDLE_ENVIRONMENT,
        'subscription': subscription,
        'org':          org,
    })


# ─────────────────────────────────────────
# CREATE CHECKOUT SESSION
# ─────────────────────────────────────────

@login_required
def create_checkout(request):
    """Return Paddle price ID for JS checkout overlay."""
    from .views import get_org
    org  = get_org(request)
    if not org:
        return JsonResponse({'error': 'No organization found'}, status=400)

    plan    = request.GET.get('plan', 'pro')
    billing = request.GET.get('billing', 'monthly')

    price_id = get_price_id(plan, billing)
    if not price_id:
        return JsonResponse({'error': 'Invalid plan'}, status=400)

    sub = getattr(org, 'subscription', None)

    return JsonResponse({
        'price_id':    price_id,
        'environment': settings.PADDLE_ENVIRONMENT,
        'customer_email': request.user.email,
        'custom_data': {
            'org_id':   org.id,
            'org_slug': org.slug,
            'plan':     plan,
            'billing':  billing,
        }
    })


# ─────────────────────────────────────────
# BILLING PORTAL
# ─────────────────────────────────────────

@login_required
def billing_portal(request):
    """Show billing status and manage subscription."""
    from .views import get_org
    org = get_org(request)
    if not org:
        return redirect('user_login')

    subscription = getattr(org, 'subscription', None)

    return render(request, 'planner/billing_portal.html', {
        'org':          org,
        'subscription': subscription,
        'prices':       settings.PADDLE_PRICES,
        'environment':  settings.PADDLE_ENVIRONMENT,
        'plan_limits':  settings.PLAN_LIMITS,
    })


@login_required
def cancel_subscription(request):
    """Cancel subscription via Paddle API."""
    from .views import get_org
    org = get_org(request)
    if not org:
        return JsonResponse({'error': 'No org'}, status=400)

    sub = getattr(org, 'subscription', None)
    if not sub or not sub.paddle_subscription_id:
        return JsonResponse({'error': 'No active subscription'}, status=400)

    try:
        client = get_paddle_client()
        if client:
            client.subscriptions.cancel(sub.paddle_subscription_id, effective_from='next_billing_period')
        sub.status = 'cancelled'
        sub.save()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────
# TASK 7 — PADDLE WEBHOOK HANDLER
# ─────────────────────────────────────────

@csrf_exempt
@require_POST
def paddle_webhook(request):
    """Handle all incoming Paddle webhook events."""
    payload   = request.body
    signature = request.headers.get('Paddle-Signature', '')

    # Verify signature
    if not verify_webhook_signature(payload, signature):
        return HttpResponse('Invalid signature', status=401)

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse('Invalid JSON', status=400)

    event_type = event.get('event_type', '')
    data       = event.get('data', {})

    # Route to correct handler
    handlers = {
        'subscription.activated':  handle_subscription_activated,
        'subscription.updated':    handle_subscription_updated,
        'subscription.canceled':   handle_subscription_canceled,
        'subscription.past_due':   handle_subscription_past_due,
        'transaction.completed':   handle_transaction_completed,
        'transaction.payment_failed': handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        try:
            handler(data)
        except Exception as e:
            print(f"Webhook handler error [{event_type}]: {e}")
            return HttpResponse('Handler error', status=500)

    return HttpResponse('OK', status=200)


def handle_subscription_activated(data):
    """Subscription started — activate org."""
    sub_id      = data.get('id')
    customer_id = data.get('customer_id')
    custom_data = data.get('custom_data', {})
    org_id      = custom_data.get('org_id')

    if not org_id:
        return

    try:
        org = Organization.objects.get(id=org_id)
        sub = org.subscription

        # Get plan from price ID
        items    = data.get('items', [])
        price_id = items[0].get('price', {}).get('id', '') if items else ''
        plan, _  = get_plan_from_price_id(price_id)

        sub.status                 = 'active'
        sub.plan                   = plan or sub.plan
        sub.paddle_subscription_id = sub_id
        sub.paddle_customer_id     = customer_id
        sub.save()

    except Organization.DoesNotExist:
        print(f"Org {org_id} not found for subscription {sub_id}")


def handle_subscription_updated(data):
    """Plan changed — update subscription."""
    sub_id      = data.get('id')
    custom_data = data.get('custom_data', {})
    org_id      = custom_data.get('org_id')

    if not org_id:
        # Try finding by paddle subscription ID
        try:
            sub = Subscription.objects.get(paddle_subscription_id=sub_id)
            items    = data.get('items', [])
            price_id = items[0].get('price', {}).get('id', '') if items else ''
            plan, _  = get_plan_from_price_id(price_id)
            if plan:
                sub.plan = plan
                sub.save()
        except Subscription.DoesNotExist:
            pass
        return

    try:
        org      = Organization.objects.get(id=org_id)
        sub      = org.subscription
        items    = data.get('items', [])
        price_id = items[0].get('price', {}).get('id', '') if items else ''
        plan, _  = get_plan_from_price_id(price_id)
        if plan:
            sub.plan = plan
        sub.status = 'active'
        sub.save()
    except Organization.DoesNotExist:
        pass


def handle_subscription_canceled(data):
    """Subscription cancelled."""
    sub_id = data.get('id')
    try:
        sub        = Subscription.objects.get(paddle_subscription_id=sub_id)
        sub.status = 'cancelled'
        sub.save()
    except Subscription.DoesNotExist:
        pass


def handle_subscription_past_due(data):
    """Payment failed — mark past due."""
    sub_id = data.get('id')
    try:
        sub        = Subscription.objects.get(paddle_subscription_id=sub_id)
        sub.status = 'past_due'
        sub.save()
    except Subscription.DoesNotExist:
        pass


def handle_transaction_completed(data):
    """Payment succeeded — ensure active."""
    sub_id = data.get('subscription_id')
    if sub_id:
        try:
            sub        = Subscription.objects.get(paddle_subscription_id=sub_id)
            sub.status = 'active'
            sub.save()
        except Subscription.DoesNotExist:
            pass


def handle_payment_failed(data):
    """Payment failed."""
    sub_id = data.get('subscription_id')
    if sub_id:
        try:
            sub        = Subscription.objects.get(paddle_subscription_id=sub_id)
            sub.status = 'past_due'
            sub.save()
        except Subscription.DoesNotExist:
            pass
