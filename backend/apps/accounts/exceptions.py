"""
Custom DRF exception handler that produces user-friendly API responses.
"""

import logging

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
        if hasattr(exc, "get_codes"):
            codes = exc.get_codes()
            if isinstance(codes, str):
                code = codes
            elif isinstance(codes, dict) and "detail" in codes:
                code = codes["detail"]
            elif isinstance(codes, dict) and "code" in codes:
                code = codes["code"]

        # SimpleJWT sometimes puts code in detail dict directly
        if isinstance(getattr(exc, "detail", None), dict) and "code" in exc.detail:
            code = exc.detail["code"]

        return Response(
            {
                "error": True,
                "code": code,
                "message": str(exc.detail),
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Validation errors
    if isinstance(exc, ValidationError):
        message = "Validation error"
        field_errors = {}

        if isinstance(exc.detail, dict):
            first_field = next(iter(exc.detail))
            first_error = exc.detail[first_field][0]
            message = str(first_error)
            # Add all field errors for frontend highlighting
            for field, errors in exc.detail.items():
                field_errors[field] = [str(e) for e in errors]
        elif isinstance(exc.detail, list):
            message = str(exc.detail[0])
        else:
            message = str(exc.detail)

        response_data = {
            "error": True,
            "code": "validation_error",
            "message": message,
        }
        if field_errors:
            response_data["errors"] = field_errors

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
        view = context.get("view")
        scope = None

        if view and hasattr(view, "throttle_classes"):
            for throttle_class in view.throttle_classes:
                if hasattr(throttle_class, "scope"):
                    scope = throttle_class.scope
                    break

        message = _THROTTLE_MESSAGES.get(scope, _DEFAULT_MESSAGE)
        retry_after = getattr(exc, "wait", None)

        response_data = {
            "error": "rate_limited",
            "code": "rate_limited",
            "message": message,
        }
        if retry_after is not None:
            response_data["retry_after"] = int(retry_after) + 1

        return Response(
            response_data,
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    return response
