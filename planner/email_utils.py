import resend
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY


def send_email(to: str, subject: str, html: str):
    """Central email sending function using Resend."""
    if not settings.RESEND_API_KEY:
        print(f"[EMAIL - no API key] To: {to} | Subject: {subject}")
        return

    resend.Emails.send({
        "from":    settings.DEFAULT_FROM_EMAIL,
        "to":      [to],
        "subject": subject,
        "html":    html,
    })


def send_verification_email(user, token):
    url = f"{settings.APP_URL}/verify-email/{token}/"
    send_email(
        to=user.email,
        subject="Verify your SprintFlow email",
        html=f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
            <h2 style="color:#4F46E5">Welcome to SprintFlow 👋</h2>
            <p>Hi {user.first_name or user.username},</p>
            <p>Please verify your email address to activate your account.</p>
            <a href="{url}" style="display:inline-block;background:#4F46E5;color:white;
               padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold">
               Verify Email
            </a>
            <p style="color:#888;font-size:13px;margin-top:24px">
                This link expires in 24 hours. If you didn't sign up for SprintFlow, ignore this email.
            </p>
        </div>
        """
    )


def send_password_reset_email(user, token):
    url = f"{settings.APP_URL}/reset-password/{token}/"
    send_email(
        to=user.email,
        subject="Reset your SprintFlow password",
        html=f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
            <h2 style="color:#4F46E5">Password Reset</h2>
            <p>Hi {user.first_name or user.username},</p>
            <p>Click the button below to reset your password. This link expires in 1 hour.</p>
            <a href="{url}" style="display:inline-block;background:#4F46E5;color:white;
               padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold">
               Reset Password
            </a>
            <p style="color:#888;font-size:13px;margin-top:24px">
                If you didn't request this, ignore this email. Your password won't change.
            </p>
        </div>
        """
    )
