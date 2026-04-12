import uuid
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
from .models import (
    Organization, Subscription, OrganizationMember,
    EmailVerificationToken, PasswordResetToken
)
from .email_utils import send_verification_email, send_password_reset_email


# ─────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────

def signup(request):
    if request.user.is_authenticated:
        return redirect('sm_panel')

    error = ''
    if request.method == 'POST':
        first_name    = request.POST.get('first_name', '').strip()
        last_name     = request.POST.get('last_name', '').strip()
        email         = request.POST.get('email', '').strip().lower()
        org_name      = request.POST.get('org_name', '').strip()
        password      = request.POST.get('password', '')
        password2     = request.POST.get('password2', '')

        # Validation
        if not all([first_name, last_name, email, org_name, password]):
            error = 'All fields are required.'
        elif password != password2:
            error = 'Passwords do not match.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif User.objects.filter(email=email).exists():
            error = 'An account with this email already exists.'
        else:
            # Email domain locking — one trial per domain
            domain = email.split('@')[1]
            existing_orgs = Organization.objects.filter(
                members__user__email__endswith=f'@{domain}'
            )
            if existing_orgs.exists():
                error = f'A team from {domain} already has an account. Ask your admin to invite you instead.'
            else:
                # Create user
                username = email  # use email as username
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=False,  # inactive until email verified
                )

                # Create organization
                base_slug = slugify(org_name)
                slug      = base_slug
                counter   = 1
                while Organization.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                org = Organization.objects.create(
                    name=org_name,
                    slug=slug,
                    owner=user,
                )

                # Create subscription — 14 day trial
                Subscription.objects.create(
                    organization=org,
                    plan='pro',
                    status='trialing',
                    trial_end=timezone.now() + timedelta(days=14),
                )

                # Create admin membership
                OrganizationMember.objects.create(
                    organization=org,
                    user=user,
                    role='admin',
                )

                # Send verification email
                token = EmailVerificationToken.objects.create(user=user)
                send_verification_email(user, token.token)

                return redirect('verify_email_sent')

    return render(request, 'planner/signup.html', {'error': error})


# ─────────────────────────────────────────
# EMAIL VERIFICATION
# ─────────────────────────────────────────

def verify_email_sent(request):
    return render(request, 'planner/verify_email_sent.html')


def verify_email(request, token):
    try:
        token_obj = EmailVerificationToken.objects.select_related('user').get(token=token)
    except EmailVerificationToken.DoesNotExist:
        return render(request, 'planner/verify_email_invalid.html')

    if token_obj.is_expired():
        token_obj.delete()
        return render(request, 'planner/verify_email_invalid.html', {'expired': True})

    user          = token_obj.user
    user.is_active = True
    user.save()
    token_obj.delete()

    login(request, user)
    return redirect('onboarding')


# ─────────────────────────────────────────
# ONBOARDING (post-verification landing)
# ─────────────────────────────────────────

@login_required
def onboarding(request):
    return render(request, 'planner/onboarding.html')


# ─────────────────────────────────────────
# LOGIN / LOGOUT
# ─────────────────────────────────────────

def user_login(request):
    if request.user.is_authenticated:
        return redirect('sm_panel')

    error = ''
    if request.method == 'POST':
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        try:
            user_obj = User.objects.get(email=email)
            user     = authenticate(request, username=user_obj.username, password=password)
            if user:
                if not user.is_active:
                    error = 'Please verify your email before logging in.'
                else:
                    login(request, user)
                    # Check how many orgs this user belongs to
                    orgs = OrganizationMember.objects.filter(
                        user=user
                    ).select_related('organization')
                    if orgs.count() > 1:
                        return redirect('select_org')
                    return redirect('sm_panel')
            else:
                error = 'Invalid email or password.'
        except User.DoesNotExist:
            error = 'Invalid email or password.'

    return render(request, 'planner/login.html', {'error': error})

@login_required
def select_org(request):
    """Show org selector when user belongs to multiple orgs."""
    memberships = OrganizationMember.objects.filter(
        user=request.user
    ).select_related('organization')

    if memberships.count() == 1:
        return redirect('sm_panel')

    if request.method == 'POST':
        org_id = request.POST.get('org_id')
        # Store selected org in session
        membership = memberships.filter(organization_id=org_id).first()
        if membership:
            request.session['active_org_id'] = int(org_id)
            return redirect('sm_panel')

    return render(request, 'planner/select_org.html', {
        'memberships': memberships
    })


def user_logout(request):
    logout(request)
    return redirect('user_login')


# ─────────────────────────────────────────
# PASSWORD RESET
# ─────────────────────────────────────────

def password_reset_request(request):
    message = ''
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        try:
            user = User.objects.get(email=email)
            # Delete old token if exists
            PasswordResetToken.objects.filter(user=user).delete()
            token = PasswordResetToken.objects.create(user=user)
            send_password_reset_email(user, token.token)
        except User.DoesNotExist:
            pass  # don't reveal if email exists
        message = 'If that email is registered, a reset link has been sent.'

    return render(request, 'planner/password_reset_request.html', {'message': message})


def password_reset_confirm(request, token):
    try:
        token_obj = PasswordResetToken.objects.select_related('user').get(token=token)
    except PasswordResetToken.DoesNotExist:
        return render(request, 'planner/password_reset_invalid.html')

    if token_obj.is_expired():
        token_obj.delete()
        return render(request, 'planner/password_reset_invalid.html', {'expired': True})

    error = ''
    if request.method == 'POST':
        password  = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != password2:
            error = 'Passwords do not match.'
        else:
            user = token_obj.user
            user.set_password(password)
            user.save()
            token_obj.delete()
            return redirect('password_reset_done')

    return render(request, 'planner/password_reset_confirm.html', {'error': error, 'token': token})


def password_reset_done(request):
    return render(request, 'planner/password_reset_done.html')
