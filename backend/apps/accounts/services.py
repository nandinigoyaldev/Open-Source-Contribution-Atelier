"""
Services for user accounts, authentication tokens, and password reset flows.
"""

import logging
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from .models import PasswordResetToken, UserSession
from .token_rotation import publish_token_revoked

logger = logging.getLogger(__name__)
User = get_user_model()

# Password reset token expiration lifetime: 15 minutes (900 seconds)
PASSWORD_RESET_TIMEOUT_SECONDS: int = getattr(
    settings, "PASSWORD_RESET_TIMEOUT_SECONDS", 900
)
PASSWORD_RESET_TIMEOUT_MINUTES: int = getattr(
    settings, "PASSWORD_RESET_TIMEOUT_MINUTES", 15
)


def revoke_user_sessions(user, keep_session_id=None, notify: bool = True) -> dict:
    """Revoke every way the user is currently signed in, optionally keeping one device.

    What is revoked:

    * all access tokens, by bumping the profile's token version (they carry the old one);
    * all refresh tokens, by blacklisting every outstanding token on the server;
    * the device list (``UserSession``), except ``keep_session_id`` when given.

    The caller issues a fresh token pair for the device it keeps *after* this runs, so the new
    tokens carry the new version and are not caught by the blacklist.

    Run it inside the same transaction as the password change so the two succeed or fail
    together. Pass ``notify=False`` there and call :func:`notify_sessions_revoked` after the
    transaction, so WebSocket clients are only told about a change that was saved.

    Returns the number of refresh tokens blacklisted and device sessions removed.
    """
    with transaction.atomic():
        profile = getattr(user, "user_profile", None)
        if profile is not None:
            profile.increment_jwt_version()

        already = set(
            BlacklistedToken.objects.filter(token__user=user).values_list(
                "token_id", flat=True
            )
        )
        pending = [
            BlacklistedToken(token=token)
            for token in OutstandingToken.objects.filter(user=user).exclude(
                pk__in=already
            )
        ]
        BlacklistedToken.objects.bulk_create(pending, ignore_conflicts=True)

        sessions = UserSession.objects.filter(user=user)
        if keep_session_id is not None:
            sessions = sessions.exclude(session_id=keep_session_id)
        removed, _ = sessions.delete()

    if notify:
        notify_sessions_revoked(user)
    return {"refresh_tokens_blacklisted": len(pending), "sessions_removed": removed}


def notify_sessions_revoked(user) -> None:
    """Tell the user's open WebSocket connections that their tokens were revoked."""
    publish_token_revoked(user.pk)


def create_password_reset_token(user) -> PasswordResetToken:
    """
    Generate a new single-use password reset token for the given user,
    invalidating any previously generated unused tokens.
    """
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
    reset_token = PasswordResetToken.objects.create(user=user)
    logger.info("Created password reset token for user_id=%s", user.id)
    return reset_token


def is_token_expired(
    reset_token: PasswordResetToken,
    timeout_seconds: int = PASSWORD_RESET_TIMEOUT_SECONDS,
) -> bool:
    """
    Return True if the token's creation timestamp exceeds the timeout threshold (15 minutes / 900s).
    """
    if not reset_token or not reset_token.created_at:
        return True
    return timezone.now() > reset_token.created_at + timedelta(seconds=timeout_seconds)


def validate_password_reset_token(
    token_value: str,
    timeout_seconds: int = PASSWORD_RESET_TIMEOUT_SECONDS,
) -> Tuple[bool, Optional[PasswordResetToken], Optional[str]]:
    """
    Validate a password reset token string.

    Returns:
        (is_valid, token_object, error_code_or_message)
    """
    try:
        reset_token = PasswordResetToken.objects.select_related("user").get(
            token=token_value,
            is_used=False,
        )
    except (PasswordResetToken.DoesNotExist, ValueError):
        return False, None, "invalid_token"

    if is_token_expired(reset_token, timeout_seconds=timeout_seconds):
        return False, reset_token, "expired_token"

    return True, reset_token, None


def redeem_password_reset_token(
    token_value: str,
    new_password: str,
    timeout_seconds: int = PASSWORD_RESET_TIMEOUT_SECONDS,
) -> Tuple[bool, Optional[str]]:
    """
    Redeem a password reset token and update the user's password.
    Rejects tokens that have expired past 15 minutes (900 seconds).

    Returns:
        (success, error_message)
    """
    is_valid, reset_token, error = validate_password_reset_token(
        token_value, timeout_seconds=timeout_seconds
    )
    if not is_valid or not reset_token:
        if error == "expired_token":
            return False, "Password reset link expired"
        return False, "This reset link is invalid or has already been used."

    user = reset_token.user
    with transaction.atomic():
        user.set_password(new_password)
        user.save()

        # Mark all unused reset tokens for this user as redeemed
        PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

        # A reset happens signed out, so every session is revoked (this also records the
        # time of the password change on the profile).
        revoke_user_sessions(user, notify=False)
    notify_sessions_revoked(user)
    logger.info("Successfully reset password for user_id=%s", user.id)
    return True, None
