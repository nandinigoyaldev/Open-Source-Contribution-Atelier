"""
Thread-local storage for per-request audit context.

Follows the exact same pattern as AdminAuditMiddleware in
apps.core.middleware and RequestIdMiddleware in
apps.core.middleware.request_id.
"""

import threading

_audit_ctx = threading.local()


def get_audit_context() -> dict:
    """Return the current request's audit context dict."""
    return {
        "actor": getattr(_audit_ctx, "actor", None),
        "ip_address": getattr(_audit_ctx, "ip_address", None),
        "user_agent": getattr(_audit_ctx, "user_agent", ""),
        "correlation_id": getattr(_audit_ctx, "correlation_id", ""),
    }


class AuditContextMiddleware:
    """
    WSGI middleware that populates _audit_ctx thread-locals with the
    authenticated user, client IP, user-agent, and correlation ID for
    every request.

    Must be placed AFTER AuthenticationMiddleware and AFTER
    RequestIdMiddleware in settings.MIDDLEWARE so that both
    request.user and request.request_id are already populated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _audit_ctx.actor = (
            request.user
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )
        _audit_ctx.ip_address = self._get_client_ip(request)
        _audit_ctx.user_agent = request.META.get("HTTP_USER_AGENT", "")
        # correlation_id is set by RequestIdMiddleware as request.request_id
        _audit_ctx.correlation_id = getattr(request, "request_id", "")

        try:
            response = self.get_response(request)
        finally:
            # Always clear to prevent bleed between requests on the same thread
            _audit_ctx.actor = None
            _audit_ctx.ip_address = None
            _audit_ctx.user_agent = ""
            _audit_ctx.correlation_id = ""

        return response

    @staticmethod
    def _get_client_ip(request) -> str | None:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
