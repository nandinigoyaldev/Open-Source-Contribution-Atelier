import logging

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
