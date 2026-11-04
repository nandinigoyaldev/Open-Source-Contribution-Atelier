import logging
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, JsonResponse

from .security import (
    audit_verification,
    check_signature,
    get_signing_keys,
    rejection_response,
)

logger = logging.getLogger(__name__)

_SIGNATURE_META_KEYS = (
    "HTTP_X_WEBHOOK_SIGNATURE_V2",
    "HTTP_X_WEBHOOK_SIGNATURE",
    "HTTP_X_SIGNATURE",
)


class WebhookSignatureMiddleware:
    """
    Middleware that enforces HMAC-SHA256 signature verification and timestamp replay protection
    for incoming webhook routes.

    Key rotation is supported via settings.WEBHOOK_SIGNING_KEYS, a list of (key_id, secret) pairs.
    Verification attempts each key. The timestamp is part of the signed material and must be within
    settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS (default: 300s) of the server clock, in either
    direction. Payload-only signatures are accepted only while
    settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES is true. See docs/WEBHOOKS.md.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if self._is_webhook_request(request):
            error_response = self._verify_webhook(request)
            if error_response:
                return error_response
        return self.get_response(request)

    def _is_webhook_request(self, request: HttpRequest) -> bool:
        path = request.path
        # Exclude management CRUD routes unless explicitly carrying signature headers
        management_routes = ["/api/webhooks/endpoints/", "/api/webhooks/deliveries/"]
        if any(path.startswith(route) for route in management_routes):
            if not any(h in request.META for h in _SIGNATURE_META_KEYS):
                return False

        prefixes = getattr(
            settings,
            "WEBHOOK_INCOMING_URL_PREFIXES",
            [
                "/api/webhooks/incoming",
                "/api/webhooks/receiver",
                "/api/notifications/webhook",
                "/webhook/",
            ],
        )
        if any(path.startswith(prefix) for prefix in prefixes):
            return True
        if any(h in request.META for h in _SIGNATURE_META_KEYS):
            return True
        return False

    def _verify_webhook(self, request: HttpRequest) -> Optional[JsonResponse]:
        signature = (
            request.META.get("HTTP_X_WEBHOOK_SIGNATURE_V2")
            or request.META.get("HTTP_X_WEBHOOK_SIGNATURE")
            or request.META.get("HTTP_X_SIGNATURE")
        )
        if not signature:
            return JsonResponse(
                {"error": "Missing X-Webhook-Signature header"}, status=401
            )

        keys = get_signing_keys()
        if not keys:
            logger.error(
                "No webhook signing key configured (settings.WEBHOOK_SIGNING_KEYS), "
                "rejecting %s",
                request.path,
            )
            return JsonResponse(
                {"error": "Configuration error: no webhook signing key"}, status=500
            )

        result = check_signature(
            keys,
            request.body,
            signature,
            timestamp=request.META.get("HTTP_X_WEBHOOK_TIMESTAMP")
            or request.META.get("HTTP_X_TIMESTAMP"),
            key_id=request.META.get("HTTP_X_WEBHOOK_KEY_ID"),
            require_timestamp=True,
        )
        audit_verification(result, request, source="middleware")
        if result.ok:
            request.webhook_key_id = result.key_id
            return None

        status, message = rejection_response(result, "Invalid webhook signature")
        return JsonResponse({"error": message}, status=status)
