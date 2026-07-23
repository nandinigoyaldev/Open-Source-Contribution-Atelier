import base64
import hashlib
import hmac
from functools import wraps
from typing import List, Tuple, Union

from django.conf import settings
from django.http import JsonResponse
from cryptography.fernet import Fernet


def get_fernet_cipher() -> Fernet:
    """
    Derives a 32-byte key for Fernet symmetric encryption from Django settings.SECRET_KEY.
    """
    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_secret(plain_text: str) -> str:
    """
    Encrypts a plaintext webhook secret using Fernet.
    """
    if not plain_text:
        return ""
    cipher = get_fernet_cipher()
    return cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_text: str) -> str:
    """
    Decrypts an encrypted webhook secret using Fernet.
    """
    if not encrypted_text:
        return ""
    cipher = get_fernet_cipher()
    return cipher.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")


def compute_signature(secret: str, payload: bytes) -> str:
    """
    Computes a SHA-256 HMAC signature for the given payload using the provided secret.
    """
    return hmac.new(
        secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
    ).hexdigest()


def verify_signature(
    secret: Union[str, List[str], Tuple[str, ...]], payload: bytes, signature: str
) -> bool:
    """
    Verifies that the provided signature matches the computed HMAC signature.
    Uses constant-time comparison to prevent timing attacks.
    Supports a list/tuple of valid secrets (e.g. for rotation grace periods).
    """
    if not signature:
        return False

    secrets = [secret] if isinstance(secret, str) else list(secret)

    for sec in secrets:
        if sec:
            expected_signature = compute_signature(sec, payload)
            if hmac.compare_digest(expected_signature, signature):
                return True
    return False


def require_webhook_signature(secret, header_name="HTTP_X_SIGNATURE"):
    """
    View decorator to enforce HMAC signature verification on incoming webhooks.

    :param secret: A string or a callable that takes the `request` and returns a string secret or list of secrets.
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
