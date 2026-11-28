"""
Applies the risk score to a password login.

Every evaluation is saved in ``UserLoginHistory``. An emailed code is only asked
for when ``LOGIN_RISK_CONFIRMATION_ENABLED`` is on and the score is above
``LOGIN_RISK_THRESHOLD``. If scoring or sending the email fails the login goes
through, so a broken lookup or mail queue never locks people out.
"""

import ipaddress
import logging
import secrets
from datetime import timedelta
from typing import NoReturn, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django_q.tasks import async_task
from rest_framework.exceptions import AuthenticationFailed

from config.db_router import use_primary

from ..models import UserLoginHistory
from ..throttles import _get_real_ip
from .risk_engine import LoginRiskAnalyzer, RiskAssessment

logger = logging.getLogger(__name__)
User = get_user_model()

CONFIRMATION_REQUIRED = "login_confirmation_required"
INVALID_CODE = "invalid_login_confirmation_code"
# How many earlier successful logins a new one is compared with.
HISTORY_WINDOW = 20


def check_login_risk(user, request, code: str = "", has_second_factor=False) -> None:
    """
    Call after the password was accepted and before any token is handed out.

    Raises ``AuthenticationFailed`` when the login has to be confirmed first.
    """
    try:
        ip_address = _clean_ip(_get_real_ip(request))
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
        with use_primary():
            history = list(
                UserLoginHistory._default_manager.filter(
                    user=user, outcome__in=UserLoginHistory.SUCCESSFUL_OUTCOMES
                )[:HISTORY_WINDOW]
            )
        assessment = LoginRiskAnalyzer().analyze(
            ip_address or "", user_agent, timezone.now(), history
        )
        entry = _build_entry(user, ip_address, user_agent, assessment)

        risky = assessment.score > getattr(settings, "LOGIN_RISK_THRESHOLD", 50)
        confirm = (
            risky
            and getattr(settings, "LOGIN_RISK_CONFIRMATION_ENABLED", False)
            # An authenticator code is already a second factor.
            and not has_second_factor
            and bool(user.email)
        )
        if not confirm:
            entry.outcome = (  # type: ignore[assignment]
                UserLoginHistory.FLAGGED if risky else UserLoginHistory.ALLOWED
            )
            entry.save()
            return
    except Exception:
        logger.exception("Login risk check failed for user_id=%s", user.pk)
        return

    if code:
        accepted = _spend_code(user, assessment.device_fingerprint, code)
        entry.outcome = (  # type: ignore[assignment]
            UserLoginHistory.CONFIRMED if accepted else UserLoginHistory.REJECTED
        )
        entry.save()
        if not accepted:
            _refuse(INVALID_CODE, "That sign-in code is wrong or has expired.")
        return

    _challenge(user, entry)


def _clean_ip(value: str) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _build_entry(
    user, ip_address, user_agent, assessment: RiskAssessment
) -> UserLoginHistory:
    info = assessment.ip_info
    return UserLoginHistory(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=assessment.device_fingerprint,
        latitude=info.latitude,
        longitude=info.longitude,
        country=info.country[:64],
        asn=info.asn,
        is_proxy=info.is_proxy,
        risk_score=assessment.score,
        reasons=assessment.reasons,
    )


def _hash_code(user, code: str) -> str:
    return salted_hmac(
        "apps.accounts.login_risk.code", f"{user.pk}:{code}", algorithm="sha256"
    ).hexdigest()


def _challenge(user, entry: UserLoginHistory) -> None:
    """Save the attempt, email a code and refuse the login for now."""
    timeout = getattr(settings, "LOGIN_RISK_CODE_TIMEOUT_MINUTES", 10)
    limit = getattr(settings, "LOGIN_RISK_MAX_CODES_PER_HOUR", 5)
    code = ""
    entry.outcome = UserLoginHistory.CHALLENGED  # type: ignore[assignment]
    with transaction.atomic():  # type: ignore[attr-defined]
        # The user row lock keeps parallel logins from passing the hourly cap.
        User.objects.select_for_update().get(pk=user.pk)
        sent = (
            UserLoginHistory._default_manager.filter(
                user=user, created_at__gte=timezone.now() - timedelta(hours=1)
            )
            .exclude(code_hash="")
            .count()
        )
        if sent < limit:
            code = f"{secrets.randbelow(10**6):06d}"
            entry.code_hash = _hash_code(user, code)  # type: ignore[assignment]
        entry.save()

    if code:
        try:
            async_task(
                "apps.accounts.tasks.send_login_confirmation_email_task",
                user_email=user.email,
                user_username=user.username,
                code=code,
                timeout=timeout,
            )
        except Exception:
            logger.exception("Could not send a login code to user_id=%s", user.pk)
            entry.outcome = UserLoginHistory.FLAGGED  # type: ignore[assignment]
            entry.code_used = True  # type: ignore[assignment]
            entry.save(update_fields=["outcome", "code_used"])
            return

    _refuse(
        CONFIRMATION_REQUIRED,
        "This sign-in looks unusual. Enter the latest code sent to your email "
        "to continue.",
    )


def _spend_code(user, fingerprint: str, code: str) -> bool:
    """True if ``code`` is the newest unused code sent for this device."""
    timeout = getattr(settings, "LOGIN_RISK_CODE_TIMEOUT_MINUTES", 10)
    max_attempts = getattr(settings, "LOGIN_RISK_MAX_CODE_ATTEMPTS", 5)
    with use_primary():
        pending = (
            UserLoginHistory._default_manager.filter(
                user=user,
                outcome=UserLoginHistory.CHALLENGED,
                device_fingerprint=fingerprint,
                created_at__gte=timezone.now() - timedelta(minutes=timeout),
            )
            .exclude(code_hash="")
            .first()
        )
    if pending is None:
        return False
    unused = UserLoginHistory._default_manager.filter(pk=pending.pk, code_used=False)
    # Count the guess before comparing, so parallel guesses cannot skip it.
    counted = unused.filter(code_attempts__lt=max_attempts).update(
        code_attempts=F("code_attempts") + 1
    )
    return bool(
        counted
        and constant_time_compare(pending.code_hash, _hash_code(user, code.strip()))
        and unused.update(code_used=True)
    )


def _refuse(error_code: str, message: str) -> NoReturn:
    raise AuthenticationFailed(
        {
            "requires_email_confirmation": True,
            "code": error_code,
            "message": message,
        },
        code=error_code,
    )
