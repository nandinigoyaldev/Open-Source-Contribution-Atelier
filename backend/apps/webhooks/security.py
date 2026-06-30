import hashlib
import hmac
from functools import wraps

from django.http import JsonResponse


def compute_signature(secret: str, payload: bytes) -> str:
    """
    Computes a SHA-256 HMAC signature for the given payload using the provided secret.
    """
    return hmac.new(
        secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
    ).hexdigest()


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    """
    Verifies that the provided signature matches the computed HMAC signature.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not signature:
        return False

    expected_signature = compute_signature(secret, payload)
    return hmac.compare_digest(expected_signature, signature)


def require_webhook_signature(secret, header_name="HTTP_X_SIGNATURE"):
    """
    View decorator to enforce HMAC signature verification on incoming webhooks.

    :param secret: A string or a callable that takes the `request` and returns a string secret.
    :param header_name: The Django META key for the header (e.g. 'HTTP_X_SIGNATURE' for 'X-Signature').
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Extract payload
            payload = request.body
            if not payload:
                return JsonResponse({"error": "Empty payload"}, status=400)

            # Extract signature
            signature = request.META.get(header_name)
            if not signature:
                return JsonResponse({"error": "Missing signature header"}, status=403)

            # Determine secret
            actual_secret = secret(request) if callable(secret) else secret
            if not actual_secret:
                return JsonResponse(
                    {"error": "Configuration error: Missing secret"}, status=500
                )

            # Verify
            if not verify_signature(actual_secret, payload, signature):
                return JsonResponse({"error": "Invalid signature"}, status=403)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
