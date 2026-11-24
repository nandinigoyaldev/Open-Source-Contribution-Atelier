import functools
import time

from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.core.permissions import (
    IsAdminOrModeratorRole,
    IsAdminRole,
    IsModeratorRole,
)


def generate_step_up_token(user, max_age_seconds: int = 300) -> str:
    """Generate a cryptographic time-stamped step-up authentication token."""
    signer = TimestampSigner(salt="accounts.step_up_auth")
    token = signer.sign(f"{user.pk}")
    cache.set(f"step_up_user_{user.pk}", time.time(), timeout=max_age_seconds)
    return token


def verify_step_up_token(token: str, user, max_age_seconds: int = 300) -> bool:
    """Verify that a step-up token is valid, unexpired, and issued to the given user."""
    if not token or not user or not user.is_authenticated:
        return False
    signer = TimestampSigner(salt="accounts.step_up_auth")
    try:
        user_id = signer.unsign(token, max_age=max_age_seconds)
        return str(user_id) == str(user.pk)
    except (BadSignature, SignatureExpired):
        return False


def is_recently_authenticated(request, user=None, max_age_seconds: int = 300) -> bool:
    """Determine whether the request is accompanied by recent authentication within max_age_seconds."""
    if user is None:
        user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False

    # 1. Flag set by middleware or previous check
    if getattr(request, "is_step_up_authenticated", False):
        return True

    # 2. Check header or request body/query for step-up token
    token = (
        request.headers.get("X-Step-Up-Token")
        or request.META.get("HTTP_X_STEP_UP_TOKEN")
    )
    if not token and hasattr(request, "data") and isinstance(request.data, dict):
        token = request.data.get("step_up_token")
    if not token and hasattr(request, "GET"):
        token = request.GET.get("step_up_token")

    if token and verify_step_up_token(token, user, max_age_seconds=max_age_seconds):
        request.is_step_up_authenticated = True
        return True

    # 3. Cache entry from recent step-up verification
    cached_timestamp = cache.get(f"step_up_user_{user.pk}")
    if cached_timestamp is not None:
        if (time.time() - float(cached_timestamp)) <= max_age_seconds:
            return True

    # 4. JWT auth claim (iat or auth_time)
    auth = getattr(request, "auth", None)
    if auth is not None and hasattr(auth, "get"):
        iat = auth.get("iat") or auth.get("auth_time")
        if iat is not None:
            token_age = time.time() - float(iat)
            if token_age <= max_age_seconds:
                return True

    # 5. Django session last_auth_time
    session = getattr(request, "session", None)
    if session is not None and hasattr(session, "get"):
        auth_time = session.get("last_auth_time")
        if auth_time is not None:
            if (time.time() - float(auth_time)) <= max_age_seconds:
                return True

    return False


class IsRecentAuthentication(BasePermission):
    """DRF Permission class enforcing recent authentication or step-up token."""

    message = (
        "Step-up authentication required: recent authentication within 5 minutes is required."
    )
    max_age_seconds = 300

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        max_age = getattr(view, "step_up_max_age_seconds", self.max_age_seconds)
        if is_recently_authenticated(request, request.user, max_age_seconds=max_age):
            return True
        raise PermissionDenied(
            {
                "error": "step_up_required",
                "detail": self.message,
                "max_age_seconds": max_age,
            }
        )


def require_recent_authentication(max_age_seconds: int = 300):
    """View decorator ensuring caller has authenticated within max_age_seconds."""

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(*args, **kwargs):
            # Locate the request object in arguments
            request = None
            for arg in args:
                if hasattr(arg, "user") and hasattr(arg, "META"):
                    request = arg
                    break
            if request is None and args:
                request = getattr(args[0], "request", None)

            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return Response(
                    {"error": "Authentication credentials were not provided."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not is_recently_authenticated(
                request, user, max_age_seconds=max_age_seconds
            ):
                return Response(
                    {
                        "error": "step_up_required",
                        "detail": "Step-up authentication required. Please re-authenticate.",
                        "max_age_seconds": max_age_seconds,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(*args, **kwargs)

        return _wrapped

    return decorator


class StepUpAuthMiddleware:
    """Middleware inspecting X-Step-Up-Token and attaching verification status."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = request.headers.get("X-Step-Up-Token") or request.META.get(
            "HTTP_X_STEP_UP_TOKEN"
        )
        user = getattr(request, "user", None)
        if token and user and user.is_authenticated:
            if verify_step_up_token(token, user):
                request.is_step_up_authenticated = True
                request.step_up_token = token
        return self.get_response(request)


__all__ = [
    "IsAdminRole",
    "IsModeratorRole",
    "IsAdminOrModeratorRole",
    "generate_step_up_token",
    "verify_step_up_token",
    "is_recently_authenticated",
    "IsRecentAuthentication",
    "require_recent_authentication",
    "StepUpAuthMiddleware",
]
