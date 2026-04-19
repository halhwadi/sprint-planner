from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.conf import settings


# URLs that are always accessible regardless of subscription status
EXEMPT_URLS = [
    '/login/',
    '/logout/',
    '/signup/',
    '/verify-email/',
    '/password-reset/',
    '/onboarding/',
    '/invite/',
    '/billing/',
    '/pricing/',
    '/privacy-policy/',
    '/terms-of-service/',
    '/refund-policy/',
    '/webhooks/',
    '/admin/',
    '/static/',
    '/',
]


class SubscriptionMiddleware:
    """
    Task 8 — Plan Gating Middleware.
    Checks subscription status on every request.
    Redirects to billing if subscription is expired or cancelled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check authenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip exempt URLs
        path = request.path_info
        if any(path.startswith(url) for url in EXEMPT_URLS):
            return self.get_response(request)

        # Get org and subscription
        from planner.models import OrganizationMember
        membership = OrganizationMember.objects.select_related(
            'organization__subscription'
        ).filter(user=request.user).first()

        if not membership:
            return self.get_response(request)

        org = membership.organization

        # Test orgs bypass all checks
        if org.is_test:
            return self.get_response(request)

        # Check subscription
        sub = getattr(org, 'subscription', None)
        if not sub:
            return redirect('/billing/')

        if not sub.is_active():
            # Grace period — past_due gets 3 days
            if sub.status == 'past_due':
                from django.utils import timezone
                from datetime import timedelta
                grace_end = sub.updated_at + timedelta(days=3)
                if timezone.now() < grace_end:
                    # Allow access but could add a warning banner
                    request.subscription_warning = 'payment_failed'
                    return self.get_response(request)
            return redirect('/billing/')

        # Attach subscription to request for use in views
        request.org         = org
        request.subscription = sub

        return self.get_response(request)


class PlanGatingMixin:
    """
    Helper mixin for views to check plan feature access.
    Use in views: self.check_feature(request, 'excel')
    """

    def check_feature(self, request, feature: str):
        """Returns True if current org's plan has access to feature."""
        org = getattr(request, 'org', None)
        if not org:
            from planner.views import get_org
            org = get_org(request)
        if not org:
            return False
        if org.is_test:
            return True
        sub    = getattr(org, 'subscription', None)
        if not sub:
            return False
        limits = settings.PLAN_LIMITS.get(sub.plan, {})
        return limits.get(feature, False)

    def check_member_limit(self, request):
        """Returns True if org is under member limit."""
        org = getattr(request, 'org', None)
        if not org:
            from planner.views import get_org
            org = get_org(request)
        if not org or org.is_test:
            return True
        sub    = getattr(org, 'subscription', None)
        if not sub:
            return False
        limits  = settings.PLAN_LIMITS.get(sub.plan, {})
        max_mem = limits.get('members')
        if max_mem is None:
            return True  # unlimited
        current = org.members.count()
        return current < max_mem


def check_plan_feature(org, feature: str) -> bool:
    """Standalone function to check plan feature access."""
    if not org:
        return False
    if org.is_test:
        return True
    sub = getattr(org, 'subscription', None)
    if not sub:
        return False
    limits = settings.PLAN_LIMITS.get(sub.plan, {})
    return bool(limits.get(feature, False))


def check_member_limit(org) -> bool:
    """Standalone function to check member limit."""
    if not org or org.is_test:
        return True
    sub = getattr(org, 'subscription', None)
    if not sub:
        return False
    limits  = settings.PLAN_LIMITS.get(sub.plan, {})
    max_mem = limits.get('members')
    if max_mem is None:
        return True
    return org.members.count() < max_mem


def check_session_limit(org) -> bool:
    """Check if org can create more planning sessions this month."""
    if not org or org.is_test:
        return True
    sub = getattr(org, 'subscription', None)
    if not sub:
        return False
    limits      = settings.PLAN_LIMITS.get(sub.plan, {})
    max_sessions = limits.get('sessions_per_month')
    if max_sessions is None:
        return True  # unlimited
    # Count sessions this month
    from django.utils import timezone
    from planner.models import Sprint
    now         = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    count       = Sprint.objects.filter(
        organization=org,
        created_at__gte=month_start
    ).count()
    return count < max_sessions
