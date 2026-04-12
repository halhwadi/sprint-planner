import json
import uuid as uuid_lib
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import InviteToken, Organization, OrganizationMember, SprintMember, Team
from .email_utils import send_invite_email
from .permissions import require_scrum_master_api, is_admin


@require_POST
@require_scrum_master_api
def send_invite(request):
    from .views import get_org
    org  = get_org(request)
    data = json.loads(request.body)

    email   = data.get('email', '').strip().lower()
    role    = data.get('role', 'voter')
    team_id = data.get('team_id')

    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)

    if role not in ('admin', 'scrum_master', 'voter', 'viewer'):
        return JsonResponse({'error': 'Invalid role'}, status=400)

    if role == 'admin' and not is_admin(request.user, org):
        return JsonResponse({'error': 'Only admins can invite admins'}, status=403)

    if OrganizationMember.objects.filter(
        organization=org, user__email=email
    ).exists():
        return JsonResponse({'error': 'This person is already a member'}, status=400)

    team = None
    if team_id:
        team = get_object_or_404(Team, id=team_id, organization=org)

    invite, _ = InviteToken.objects.update_or_create(
        organization=org,
        email=email,
        defaults={
            'invited_by': request.user,
            'role':       role,
            'team':       team,
            'status':     'pending',
            'token':      uuid_lib.uuid4(),
        }
    )

    send_invite_email(request.user, invite, org)
    return JsonResponse({'ok': True, 'email': email, 'role': role})


@require_POST
@require_scrum_master_api
def cancel_invite(request, invite_id):
    from .views import get_org
    org    = get_org(request)
    invite = get_object_or_404(InviteToken, id=invite_id, organization=org)
    invite.delete()
    return JsonResponse({'ok': True})


def accept_invite(request, token):
    invite = get_object_or_404(InviteToken, token=token, status='pending')

    if invite.is_expired():
        invite.status = 'expired'
        invite.save()
        return render(request, 'planner/invite_expired.html')

    if OrganizationMember.objects.filter(
        organization=invite.organization,
        user__email=invite.email
    ).exists():
        return render(request, 'planner/invite_already_member.html', {
            'org': invite.organization
        })

    existing_user = User.objects.filter(email=invite.email).first()
    if existing_user:
        if request.method == 'POST':
            OrganizationMember.objects.create(
                organization=invite.organization,
                user=existing_user,
                role=invite.role,
            )
            SprintMember.objects.get_or_create(
                organization=invite.organization,
                user=existing_user,
                defaults={
                    'is_active': True,
                    'team':      invite.team,
                }
            )
            invite.status = 'accepted'
            invite.save()
            login(request, existing_user)
            return redirect('sm_panel')

        return render(request, 'planner/invite_confirm.html', {
            'invite':        invite,
            'existing_user': True,
            'email':         invite.email,
            'org':           invite.organization,
            'role':          invite.get_role_display(),
            'team':          invite.team,
        })

    error = ''
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        password   = request.POST.get('password', '')
        password2  = request.POST.get('password2', '')

        if not all([first_name, last_name, password]):
            error = 'All fields are required.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != password2:
            error = 'Passwords do not match.'
        else:
            user = User.objects.create_user(
                username=invite.email,
                email=invite.email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            OrganizationMember.objects.create(
                organization=invite.organization,
                user=user,
                role=invite.role,
            )
            SprintMember.objects.get_or_create(
                organization=invite.organization,
                user=user,
                defaults={
                    'is_active': True,
                    'team':      invite.team,
                }
            )
            invite.status = 'accepted'
            invite.save()
            login(request, user)
            return redirect('sm_panel')

    return render(request, 'planner/invite_confirm.html', {
        'invite':        invite,
        'existing_user': False,
        'email':         invite.email,
        'org':           invite.organization,
        'role':          invite.get_role_display(),
        'team':          invite.team,
        'error':         error,
    })


@login_required
def list_invites(request):
    from .views import get_org
    from .permissions import is_scrum_master_or_above
    org = get_org(request)
    if not org or not is_scrum_master_or_above(request.user, org):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    invites = InviteToken.objects.filter(
        organization=org, status='pending'
    ).select_related('invited_by', 'team').order_by('-created_at')

    return JsonResponse({
        'invites': [
            {
                'id':         i.id,
                'email':      i.email,
                'role':       i.role,
                'team':       i.team.name if i.team else None,
                'invited_by': i.invited_by.get_full_name() or i.invited_by.username,
                'created_at': i.created_at.strftime('%Y-%m-%d'),
                'expired':    i.is_expired(),
            }
            for i in invites
        ]
    })
