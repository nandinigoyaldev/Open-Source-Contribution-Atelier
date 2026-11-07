"""
Services for user accounts, authentication tokens, and password reset flows.
"""

import logging
from datetime import timedelta
from typing import Any, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.audit.models import AuditEvent
from apps.audit.security_events import record_security_event
from config.db_router import use_primary

from .models import PasswordResetToken, UserSession
from .throttles import _get_real_ip
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

# Audit operations for the reset flow. Filter with ?operation=password_reset.failed.
PASSWORD_RESET_REQUESTED = "password_reset.requested"
PASSWORD_RESET_SUPPRESSED = "password_reset.suppressed"
PASSWORD_RESET_COMPLETED = "password_reset.completed"
PASSWORD_RESET_FAILED = "password_reset.failed"
PASSWORD_RESET_RATE_LIMITED = "password_reset.rate_limited"

# One audit row per address per stage in this window, however long a flood goes on.
PASSWORD_RESET_RATE_LIMIT_AUDIT_SECONDS = 900


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


def password_reset_client(request) -> dict:
    """What the audit trail keeps about a caller, as plain values a queued task can carry."""
    return {
        "ip_address": _get_real_ip(request) or None,
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "request_id": str(getattr(request, "request_id", "")),
    }


def _email_fingerprint(email: Any) -> str:
    """
    Short keyed hash of an address, so repeats can be grouped without storing an
    address that may not belong to anyone. Kept under 32 characters so redact()
    does not take it for a credential.
    """
    normalized = str(email).strip().lower()
    return salted_hmac(
        "apps.accounts.password_reset.email", normalized, algorithm="sha256"
    ).hexdigest()[:16]


def _record_password_reset_event(
    operation: str,
    *,
    user_id: Any = None,
    client: Optional[dict] = None,
    action: str = AuditEvent.ACTION_CREATED,
    **payload: Any,
) -> None:
    record_security_event(
        operation=operation,
        action=action,
        target_type="auth.user",
        target_id=user_id if user_id is not None else "unknown",
        payload=payload,
        **(client or {}),
    )


def record_password_reset_failure(
    stage: str,
    reset_token: Optional[PasswordResetToken],
    error: Optional[str],
    client: Optional[dict] = None,
) -> None:
    """Audit a rejected token. The reason is more exact than what the caller is told."""
    if reset_token is None:
        reason = "unknown_token"
    elif error == "expired_token":
        reason = "expired_token"
    else:
        reason = "used_token"
    user_id = reset_token.user_id if reset_token is not None else None  # type: ignore[attr-defined]
    logger.warning(
        "Rejected password reset token stage=%s reason=%s user_id=%s",
        stage,
        reason,
        user_id,
    )
    _record_password_reset_event(
        PASSWORD_RESET_FAILED,
        user_id=user_id,
        client=client,
        stage=stage,
        reason=reason,
    )


def record_password_reset_rate_limited(
    stage: str, client: dict, email: Any = None
) -> None:
    """Audit a blocked caller, once per address and stage per window."""
    key = f"password_reset:rate_limited:{stage}:{client.get('ip_address')}"
    if not cache.add(key, 1, PASSWORD_RESET_RATE_LIMIT_AUDIT_SECONDS):
        return
    payload: dict = {"stage": stage}
    if email:
        payload["email_fingerprint"] = _email_fingerprint(email)
    _record_password_reset_event(PASSWORD_RESET_RATE_LIMITED, client=client, **payload)


def create_password_reset_token(user) -> PasswordResetToken:
    """
    Generate a new single-use password reset token for the given user,
    invalidating any previously generated unused tokens.

    The raw value is only on the returned instance, as ``token``.
    """
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
    reset_token = PasswordResetToken.objects.create(user=user)
    logger.info("Created password reset token for user_id=%s", user.id)
    return reset_token


def issue_password_reset(
    email: str, client: Optional[dict] = None
) -> Optional[PasswordResetToken]:
    """
    Worker half of a reset request. The view only queues this, so looking up the
    account, creating the token and sending the email all happen away from the
    request and cannot change what the caller sees or how long it takes.

    The per-hour cap counts the account's own tokens, so it holds however the
    request throttles were passed.

    Returns the new token, or None when there is nothing to send.
    """
    limit = getattr(settings, "PASSWORD_RESET_MAX_PER_HOUR", 5)
    window_start = timezone.now() - timedelta(hours=1)
    reset_token = None
    recent = 0
    with transaction.atomic():
        # Holding the user row keeps two queued requests from both passing the
        # cap or both leaving a live token behind.
        user = User.objects.select_for_update().filter(email__iexact=email).first()
        if user is not None:
            recent = PasswordResetToken._default_manager.filter(
                user=user, created_at__gte=window_start
            ).count()
            if recent < limit:
                reset_token = create_password_reset_token(user)

    if user is None:
        _record_password_reset_event(
            PASSWORD_RESET_REQUESTED,
            client=client,
            account_found=False,
            email_fingerprint=_email_fingerprint(email),
        )
    elif reset_token is None:
        logger.warning("Password reset cap reached for user_id=%s", user.pk)
        _record_password_reset_event(
            PASSWORD_RESET_SUPPRESSED,
            user_id=user.pk,
            client=client,
            recent_requests=recent,
        )
    else:
        _record_password_reset_event(
            PASSWORD_RESET_REQUESTED,
            user_id=user.pk,
            client=client,
            account_found=True,
        )
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
    token_value: Any,
    timeout_seconds: int = PASSWORD_RESET_TIMEOUT_SECONDS,
) -> Tuple[bool, Optional[PasswordResetToken], Optional[str]]:
    """
    Validate a raw password reset token.

    Returns:
        (is_valid, token_object, error_code). The error code is "invalid_token" or
        "expired_token". token_object is None only when there is no such token.
    """
    try:
        token_hash = PasswordResetToken.hash_token(token_value)
    except ValueError:
        return False, None, "invalid_token"

    # A replica could still show a spent token as unused.
    with use_primary():
        reset_token = PasswordResetToken._default_manager.filter(
            token_hash=token_hash
        ).first()

    if reset_token is None:
        return False, None, "invalid_token"

    if reset_token.is_used:
        return False, reset_token, "invalid_token"

    if is_token_expired(reset_token, timeout_seconds=timeout_seconds):
        return False, reset_token, "expired_token"

    return True, reset_token, None


def redeem_password_reset_token(
    token_value: Any,
    new_password: str,
    timeout_seconds: int = PASSWORD_RESET_TIMEOUT_SECONDS,
    client: Optional[dict] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Redeem a password reset token and update the user's password. This is the only
    place a reset token gets spent.
    Rejects tokens that have expired past 15 minutes (900 seconds).

    Returns:
        (success, error_code). The error code is "invalid_token" or "expired_token".
    """
    with transaction.atomic():
        is_valid, reset_token, error = validate_password_reset_token(
            token_value, timeout_seconds=timeout_seconds
        )
        if not is_valid or not reset_token:
            record_password_reset_failure("confirm", reset_token, error, client)
            return False, error

        user = User.objects.select_for_update().get(pk=reset_token.user_id)  # type: ignore[attr-defined]

        # Single use comes from this UPDATE, not from the read above: only one caller
        # can flip is_used, whatever the others saw. It holds where the row lock does
        # nothing (SQLite) and it means the loser of a race changes no password.
        claimed = PasswordResetToken._default_manager.filter(
            pk=reset_token.pk, is_used=False
        ).update(is_used=True)
        if not claimed:
            record_password_reset_failure("confirm", reset_token, "used", client)
            return False, "invalid_token"

        user.set_password(new_password)
        user.save()

        # Mark all unused reset tokens for this user as redeemed
        PasswordResetToken._default_manager.filter(user=user, is_used=False).update(
            is_used=True
        )

        # A reset happens signed out, so every session is revoked (this also records the
        # time of the password change on the profile).
        revoke_user_sessions(user, notify=False)
    notify_sessions_revoked(user)
    _record_password_reset_event(
        PASSWORD_RESET_COMPLETED,
        user_id=user.pk,
        client=client,
        action=AuditEvent.ACTION_UPDATED,
    )
    logger.info("Successfully reset password for user_id=%s", user.id)
    return True, None
