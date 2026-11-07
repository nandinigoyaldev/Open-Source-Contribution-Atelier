import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_password_reset_email_task(user_email, user_username, reset_url, timeout):
    """
    Sends a password reset email to the user asynchronously. (CRITICAL)
    """
    send_mail(
        subject="Password Reset Request",
        message=(
            f"Hi {user_username},\n\n"
            f"Click the link below to reset your password (expires in {timeout} minutes):\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can safely ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        recipient_list=[user_email],
        fail_silently=False,
    )


def process_password_reset_request(
    email, ip_address=None, user_agent="", request_id=""
):
    """
    Worker half of POST /api/auth/password-reset/, queued for every valid request
    whether or not the account exists. The raw token is created here and goes
    straight into the email, so it is never written to the queue or its results.
    """
    from .services import issue_password_reset
    from .views import frontend_url

    reset_token = issue_password_reset(
        email,
        client={
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_id": request_id,
        },
    )
    if reset_token is None:
        return

    user: Any = reset_token.user
    send_password_reset_email_task(
        user_email=user.email,
        user_username=user.username,
        reset_url=frontend_url("/reset-password", {"token": str(reset_token.token)}),
        timeout=getattr(settings, "PASSWORD_RESET_TIMEOUT_MINUTES", 15),
    )


def send_otp_email_task(user_email, user_username, otp_token):
    """
    Sends an OTP verification email to the user asynchronously. (CRITICAL)
    """
    send_mail(
        subject="Your Verification Code",
        message=f"Hi {user_username},\n\nYour verification code is: {otp_token}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        recipient_list=[user_email],
        fail_silently=False,
    )


def send_magic_link_email_task(user_email, user_username, login_url, timeout):
    """
    Sends a magic link email to the user asynchronously. (CRITICAL)
    """
    send_mail(
        subject="Your Magic Login Link",
        message=(
            f"Hi {user_username},\n\n"
            f"Click the link below to securely log into your account (expires in {timeout} minutes):\n"
            f"{login_url}\n\n"
            "If you did not request this, you can safely ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        recipient_list=[user_email],
        fail_silently=False,
    )


def send_verification_email_task(user_email, user_username, verify_url, timeout_hours):
    """
    Sends the email address verification link after signup. (CRITICAL)
    """
    send_mail(
        subject="Verify your email address",
        message=(
            f"Hi {user_username},\n\n"
            "Please confirm this is your email address by opening the link below "
            f"(it expires in {timeout_hours} hours):\n"
            f"{verify_url}\n\n"
            "If you did not create an Atelier account, you can safely ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        recipient_list=[user_email],
        fail_silently=False,
    )


def send_notification_email_task(user_email, subject, message_body):
    """
    Sends a general system notification email asynchronously. (NON-CRITICAL)
    Aborts execution if the user has enabled 'Do Not Disturb' (#413).
    """
    User = get_user_model()
    user = User.objects.filter(email__iexact=user_email).first()

    # Intercept and drop the email if the user profile has DND toggled on
    # We must use 'user_profile' because models.py defines related_name="user_profile"
    if user and hasattr(user, "user_profile") and user.user_profile.do_not_disturb:
        return "Email skipped: User has 'Do Not Disturb' enabled."

    send_mail(
        subject=subject,
        message=message_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        recipient_list=[user_email],
        fail_silently=False,
    )
    return f"Email sent successfully to {user_email}"


def purge_expired_sessions_task():
    """
    Daily background task to purge expired JWT tokens, database sessions, and stale transient tokens.
    """
    from django.core.management import call_command

    logger.info("Starting scheduled session purge...")
    call_command("purge_sessions")
    logger.info("Scheduled session purge complete.")
