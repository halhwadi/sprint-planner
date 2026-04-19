import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
from .models import (
    Organization, OrganizationMember, SprintMember,
    Stream, Team, Subscription, InviteToken
)
from .permissions import require_admin, require_admin_api, is_admin
from .middleware import check_plan_feature, check_member_limit


# ─────────────────────────────────────────
# ADMIN DASHBOARD
# ─────────────────────────────────────────

@require_admin
def admin_dashboard(request):
    from .views import get_org
    org          = get_org(request)
    subscription = getattr(org, 'subscription', None)
    members      = OrganizationMember.objects.filter(
        organization=org
    ).select_related('user', 'user__sprint_memberships')
    teams        = Team.objects.filter(organization=org)
    streams      = Stream.objects.filter(organization=org)
    invites      = InviteToken.objects.filter(organization=org, status='pending')
    plan_limits  = settings.PLAN_LIMITS.get(
        subscription.plan if subscription else 'starter', {}
    )

    return render(request, 'planner/admin_dashboard.html', {
        'org':          org,
        'subscription': subscription,
        'members':      members,
        'teams':        teams,
        'streams':      streams,
        'invites':      invites,
        'plan_limits':  plan_limits,
        'roles':        OrganizationMember.ROLE_CHOICES,
    })


# ─────────────────────────────────────────
# ORG SETTINGS
# ─────────────────────────────────────────

@require_POST
@require_admin_api
def update_org_settings(request):
    from .views import get_org
    org  = get_org(request)
    data = json.loads(request.body)

    if 'name' in data and data['name'].strip():
        org.name = data['name'].strip()

    if 'voting_scale' in data:
        # Store voting scale in org settings
        valid_scales = ['fibonacci', 'modified_fibonacci', 'powers_of_2', 'tshirt']
        if data['voting_scale'] in valid_scales:
            org.voting_scale = data['voting_scale']

    org.save()
    return JsonResponse({'ok': True})


# ─────────────────────────────────────────
# TEAM MANAGEMENT
# ─────────────────────────────────────────

@require_POST
@require_admin_api
def add_team(request):
    from .views import get_org
    org  = get_org(request)
    data = json.loads(request.body)
    name = data.get('name', '').strip()

    if not name:
        return JsonResponse({'error': 'Team name required'}, status=400)

    # Check team limit
    limits    = settings.PLAN_LIMITS.get(
        org.subscription.plan if hasattr(org, 'subscription') else 'starter', {}
    )
    max_teams = limits.get('teams')
    if max_teams and Team.objects.filter(organization=org).count() >= max_teams:
        return JsonResponse({
            'error': f'Your plan allows up to {max_teams} teams. Upgrade to add more.'
        }, status=403)

    team, created = Team.objects.get_or_create(
        organization=org,
        name=name,
        defaults={'created_by': request.user, 'description': data.get('description', '')}
    )
    if not created:
        return JsonResponse({'error': 'A team with this name already exists'}, status=400)

    return JsonResponse({'ok': True, 'id': team.id, 'name': team.name})


@require_POST
@require_admin_api
def edit_team(request, team_id):
    from .views import get_org
    org  = get_org(request)
    team = get_object_or_404(Team, id=team_id, organization=org)
    data = json.loads(request.body)

    if 'name' in data and data['name'].strip():
        team.name = data['name'].strip()
    if 'description' in data:
        team.description = data['description']
    team.save()
    return JsonResponse({'ok': True})


@require_POST
@require_admin_api
def delete_team(request, team_id):
    from .views import get_org
    org  = get_org(request)
    team = get_object_or_404(Team, id=team_id, organization=org)
    team.delete()
    return JsonResponse({'ok': True})


# ─────────────────────────────────────────
# MEMBER MANAGEMENT
# ─────────────────────────────────────────

@require_POST
@require_admin_api
def update_member_team(request, member_id):
    """Assign a sprint member to a team."""
    from .views import get_org
    org    = get_org(request)
    member = get_object_or_404(SprintMember, id=member_id, organization=org)
    data   = json.loads(request.body)

    team_id = data.get('team_id')
    if team_id:
        team         = get_object_or_404(Team, id=team_id, organization=org)
        member.team  = team
    else:
        member.team  = None
    member.save()
    return JsonResponse({'ok': True})


@require_POST
@require_admin_api
def update_member_stream(request, member_id):
    """Assign a sprint member to a stream."""
    from .views import get_org
    org    = get_org(request)
    member = get_object_or_404(SprintMember, id=member_id, organization=org)
    data   = json.loads(request.body)

    stream_id = data.get('stream_id')
    if stream_id:
        stream        = get_object_or_404(Stream, id=stream_id, organization=org)
        member.stream = stream
    else:
        member.stream = None
    member.save()
    return JsonResponse({'ok': True})


# ─────────────────────────────────────────
# STREAM MANAGEMENT
# ─────────────────────────────────────────

@require_POST
@require_admin_api
def edit_stream(request, stream_id):
    from .views import get_org
    org    = get_org(request)
    stream = get_object_or_404(Stream, id=stream_id, organization=org)
    data   = json.loads(request.body)

    if 'name' in data and data['name'].strip():
        stream.name = data['name'].strip()
    if 'order' in data:
        stream.order = data['order']
    stream.save()
    return JsonResponse({'ok': True})
