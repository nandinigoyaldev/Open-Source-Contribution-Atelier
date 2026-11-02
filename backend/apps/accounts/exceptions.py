"""
Custom DRF exception handler that produces user-friendly API responses.
"""

import logging
from typing import Optional

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

# Map throttle scope names → human-readable messages
_THROTTLE_MESSAGES = {
    "auth_login": "Too many login attempts. Please wait a minute and try again.",
    "auth_signup": "Too many sign-up requests. Please try again later.",
    "auth_token_refresh": "Too many token refresh requests. Please slow down.",
    "auth_otp_generate": "Too many OTP requests. Please wait a few minutes before requesting a new code.",
    "auth_otp_verify": "Too many OTP verification attempts. Please wait before trying again.",
    "auth_password_reset": "Too many password reset requests. Please wait an hour before requesting another reset.",
    "auth_oauth": "Too many OAuth requests. Please wait a moment and try again.",
    "auth_magic_link_request": "Too many magic link requests. Please wait a few minutes before requesting a new link.",
    "auth_magic_link_verify": "Too many magic link verification attempts. Please wait before trying again.",
}

_DEFAULT_MESSAGE = "Request limit exceeded. Please wait before retrying."


def throttle_exception_handler(exc, context):
    """
    Custom DRF exception handler that standardizes API error responses.
    """

    response = exception_handler(exc, context)

    if response is None:
        request = context.get("request")

        logger.exception(
            "Internal server error",
            extra={
                "path": request.path if request else None,
                "method": request.method if request else None,
            },
        )
    # Authentication required
    if isinstance(exc, NotAuthenticated):
        code = "authentication_required"
        if hasattr(exc, "get_codes"):
            codes = exc.get_codes()
            if isinstance(codes, str):
                code = codes
            elif isinstance(codes, dict) and "detail" in codes:
                code = codes["detail"]
        return Response(
            {
                "error": True,
                "code": code,
                "message": str(exc.detail),
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Invalid credentials / authentication failure
    if isinstance(exc, AuthenticationFailed):
        code = "authentication_failed"
        detail = getattr(exc, "detail", None)
        payload: dict = {}
        message: Optional[str] = None

        if isinstance(detail, dict):
            # Keep machine-readable flags (requires_2fa, field errors, ...) in
            # the body so clients can branch on them instead of parsing prose.
            for key, value in detail.items():
                payload[key] = value

            explicit_code = detail.get("code")
            if isinstance(explicit_code, str) and explicit_code:
                code = explicit_code
            elif detail.get("requires_2fa"):
                code = "2fa_required"

            if isinstance(detail.get("message"), str) and detail["message"].strip():
                message = detail["message"].strip()
            else:
                message = next(
                    (
                        str(value)
                        for value in detail.values()
                        if isinstance(value, str) and value.strip()
                    ),
                    None,
                )
        elif isinstance(detail, (list, tuple)) and detail:
            message = str(detail[0])
        elif isinstance(detail, str) and detail:
            message = detail

        if hasattr(exc, "get_codes"):
            codes = exc.get_codes()
            if code == "authentication_failed":
                if isinstance(codes, str) and codes:
                    code = codes
                elif isinstance(codes, dict):
                    if isinstance(codes.get("detail"), str):
                        code = codes["detail"]
                    elif isinstance(codes.get("code"), str):
                        code = codes["code"]

        response_data: dict = dict(payload)
        response_data["error"] = True
        response_data["code"] = code
        response_data["message"] = message or str(detail)

        return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)

    # Validation errors
    if isinstance(exc, ValidationError):
        messages, codes = _flatten_validation_detail(exc.detail)
        field_errors = {field: texts for field, texts in messages.items() if field}
        field_codes = {field: names for field, names in codes.items() if field}
        first = next(iter(messages.values()), None)

        response_data = {
            "error": True,
            "code": "validation_error",
            "message": first[0] if first else "Validation error",
        }
        if field_errors:
            # Field -> messages, for highlighting fields; error_codes has the same shape with
            # stable machine-readable codes (e.g. "email_taken") so clients never parse prose.
            response_data["errors"] = field_errors
            response_data["error_codes"] = field_codes

        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, PermissionDenied):
        return Response(
            {
                "error": True,
                "code": "permission_denied",
                "message": str(exc.detail),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Rate limiting
    if isinstance(exc, Throttled):
        import time

        view = context.get("view")
        scope = None

        if view and hasattr(view, "throttle_classes"):
            for throttle_class in view.throttle_classes:
                if hasattr(throttle_class, "scope"):
                    scope = throttle_class.scope
                    break

        message = _THROTTLE_MESSAGES.get(scope, _DEFAULT_MESSAGE)
        retry_after = getattr(exc, "wait", None)
        wait_secs = int(retry_after) + 1 if retry_after is not None else 60

        response_data = {
            "error": "rate_limited",
            "code": "rate_limited",
            "message": message,
            "retry_after": wait_secs,
        }

        response = Response(
            response_data,
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(wait_secs)
        response["X-RateLimit-Limit"] = str(getattr(exc, "limit", 100))
        response["X-RateLimit-Remaining"] = "0"
        response["X-RateLimit-Reset"] = str(int(time.time() + wait_secs))

        return response

    return response


def _flatten_validation_detail(detail):
    """
    Turn any DRF ValidationError detail into ({field: [messages]}, {field: [codes]}).

    Handles a dict of lists, a plain list, a string, and nested serializers or list fields
    (nested keys are joined with a dot: "profile.timezone", "items.0.name"). Errors that
    belong to no field are filed under "" and are used for `message` only.
    """
    messages = {}
    codes = {}

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, (list, tuple)):
            if all(not isinstance(item, (dict, list, tuple)) for item in node):
                for item in node:
                    messages.setdefault(path, []).append(str(item))
                    codes.setdefault(path, []).append(
                        getattr(item, "code", None) or "invalid"
                    )
            else:
                for index, item in enumerate(node):
                    if isinstance(item, (dict, list, tuple)):
                        walk(item, f"{path}.{index}" if path else str(index))
                    else:
                        messages.setdefault(path, []).append(str(item))
                        codes.setdefault(path, []).append(
                            getattr(item, "code", None) or "invalid"
                        )
        else:
            messages.setdefault(path, []).append(str(node))
            codes.setdefault(path, []).append(getattr(node, "code", None) or "invalid")

    walk(detail, "")
    return messages, codes
