import hashlib
import hmac
import json
from django.conf import settings


def get_paddle_client():
    """Get configured Paddle API client."""
    try:
        from paddle import Client, Environment
        env = Environment.PRODUCTION if settings.PADDLE_ENVIRONMENT == 'production' else Environment.SANDBOX
        return Client(settings.PADDLE_API_KEY, options={'environment': env})
    except Exception as e:
        print(f"Paddle client error: {e}")
        return None


def get_price_id(plan, billing):
    """Get Paddle price ID for plan + billing combination."""
    key = f"{plan}_{billing}"
    return settings.PADDLE_PRICES.get(key, '')


def verify_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """Verify Paddle webhook signature."""
    if not settings.PADDLE_WEBHOOK_SECRET:
        return True  # skip verification in dev

    try:
        # Paddle sends: ts=timestamp;h1=signature
        parts = dict(p.split('=', 1) for p in signature_header.split(';'))
        ts        = parts.get('ts', '')
        h1        = parts.get('h1', '')
        signed    = f"{ts}:{payload.decode('utf-8')}"
        expected  = hmac.new(
            settings.PADDLE_WEBHOOK_SECRET.encode(),
            signed.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception as e:
        print(f"Webhook signature error: {e}")
        return False


def get_plan_from_price_id(price_id: str) -> tuple:
    """Return (plan, billing) from a Paddle price ID."""
    for key, pid in settings.PADDLE_PRICES.items():
        if pid == price_id:
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                return parts[0], parts[1]
    return None, None


def get_plan_limits(plan: str) -> dict:
    """Get feature limits for a plan."""
    return settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS['starter'])
