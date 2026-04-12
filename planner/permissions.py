from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from .models import OrganizationMember


def get_org_member(user, org):
    """Get OrganizationMember for user in org. Returns None if not a member."""
    try:
        return OrganizationMember.objects.select_related('organization').get(
            user=user, organization=org
        )
    except OrganizationMember.DoesNotExist:
        return None


# ─────────────────────────────────────────
# ROLE CHECKS
# ─────────────────────────────────────────

def is_admin(user, org):
    m = get_org_member(user, org)
    return m is not None and m.role == 'admin'


def is_scrum_master_or_above(user, org):
    m = get_org_member(user, org)
    return m is not None and m.role in ('admin', 'scrum_master')


def can_vote(user, org):
    m = get_org_member(user, org)
    return m is not None and m.role in ('admin', 'scrum_master', 'voter')


def can_view(user, org):
    m = get_org_member(user, org)
    return m is not None


# ─────────────────────────────────────────
# DECORATORS — for regular views
# ─────────────────────────────────────────

def require_org_member(view_func):
    """User must be logged in and a member of any org."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('user_login')
        from .views import get_org
        org = get_org(request)
        if not org:
            return redirect('user_login')
        if not can_view(request.user, org):
            return redirect('user_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_scrum_master(view_func):
    """User must be SM or Admin."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('user_login')
        from .views import get_org
        org = get_org(request)
        if not org or not is_scrum_master_or_above(request.user, org):
            return redirect('board')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_admin(view_func):
    """User must be Admin."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('user_login')
        from .views import get_org
        org = get_org(request)
        if not org or not is_admin(request.user, org):
            return redirect('sm_panel')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_voter(view_func):
    """User must be able to vote (admin, SM, voter)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('user_login')
        from .views import get_org
        org = get_org(request)
        if not org or not can_vote(request.user, org):
            return redirect('board')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────
# DECORATORS — for AJAX/API views
# ─────────────────────────────────────────

def require_scrum_master_api(view_func):
    """API version — returns 403 JSON instead of redirect."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from .views import get_org
        org = get_org(request)
        if not org or not is_scrum_master_or_above(request.user, org):
            return JsonResponse({'error': 'Scrum Master or Admin role required'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_admin_api(view_func):
    """API version — returns 403 JSON instead of redirect."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from .views import get_org
        org = get_org(request)
        if not org or not is_admin(request.user, org):
            return JsonResponse({'error': 'Admin role required'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_voter_api(view_func):
    """API version — returns 403 JSON instead of redirect."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from .views import get_org
        org = get_org(request)
        if not org or not can_vote(request.user, org):
            return JsonResponse({'error': 'Voter role or above required'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper
