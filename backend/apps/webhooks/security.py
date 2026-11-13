import base64
import hashlib
import hmac
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.fernet import Fernet
from django.conf import settings
from django.http import JsonResponse

audit_logger = logging.getLogger("audit")

SIGNATURE_PREFIX = "sha256="
# Header carrying the timestamp-bound signature. The older X-Webhook-Signature
# header is payload-only and is kept for one release (see docs/WEBHOOKS.md).
SIGNATURE_V2_HEADER = "X-Webhook-Signature-V2"
TIMESTAMP_HEADER = "X-Webhook-Timestamp"
KEY_ID_HEADER = "X-Webhook-Key-Id"

DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300
# Only ever used when DEBUG is on and no signing key is configured.
DEV_FALLBACK_SECRET = "default-webhook-secret-key-change-in-production"

# Canonical forms. Anything else is rejected before any HMAC work is done, which
# also keeps non-ASCII input away from hmac.compare_digest (it raises TypeError
# on non-ASCII str).
_SIGNATURE_RE = re.compile(r"(?:sha256=)?[0-9a-f]{64}")
# Unix seconds, optional fraction. No sign, exponent, whitespace, nan or inf.
_TIMESTAMP_RE = re.compile(r"[0-9]{1,12}(?:\.[0-9]{1,9})?")
_LOG_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:/-]")


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


def serialize_payload(payload: Any) -> bytes:
    """
    The exact bytes of an outgoing delivery body. Sign these bytes and send
    these bytes (``data=body``, not ``json=payload``), otherwise the receiver
    verifies a different byte string than the one that was signed.
    """
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def compute_signature(
    secret: str, payload: bytes, timestamp: Union[str, int, None] = None
) -> str:
    """
    SHA-256 HMAC (hex) of the payload.

    Without ``timestamp`` this is the legacy payload-only signature. With a
    timestamp the signed material is ``b"<timestamp>." + payload``, so the
    timestamp cannot be swapped without invalidating the signature.
    """
    message = payload
    if timestamp is not None:
        message = f"{timestamp}.".encode("utf-8") + payload
    return hmac.new(
        secret.encode("utf-8"), msg=message, digestmod=hashlib.sha256
    ).hexdigest()


def build_signature_headers(
    secret: str, body: bytes, now: Optional[float] = None
) -> Dict[str, str]:
    """
    Signature headers for one outgoing delivery attempt. Call this for every
    attempt (retries included) so the timestamp is fresh.
    """
    timestamp = str(int(time.time() if now is None else now))
    headers = {
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_V2_HEADER: SIGNATURE_PREFIX
        + compute_signature(secret, body, timestamp),
    }
    if getattr(settings, "WEBHOOK_SEND_LEGACY_SIGNATURE", True):
        headers["X-Webhook-Signature"] = compute_signature(secret, body)
    return headers


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    # "ok", or why it was rejected: missing_signature, bad_signature_format,
    # missing_timestamp, bad_timestamp, stale_timestamp, future_timestamp,
    # unknown_key_id, legacy_signature_rejected, signature_mismatch
    reason: str
    key_id: Optional[str] = None
    legacy: bool = False
    skew_seconds: Optional[float] = None
    claimed_key_id: Optional[str] = None
    timestamp: Optional[str] = None

    def __bool__(self) -> bool:
        return self.ok


def get_timestamp_tolerance() -> int:
    value = getattr(settings, "WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS", None)
    if value is None:
        # Name used by the middleware and the GitHub view before this setting.
        value = getattr(
            settings,
            "WEBHOOK_TIMESTAMP_WINDOW_SECONDS",
            DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
        )
    return int(value)


def legacy_signatures_allowed() -> bool:
    return bool(getattr(settings, "WEBHOOK_ALLOW_LEGACY_SIGNATURES", True))


def get_signing_keys(dev_fallback: bool = True) -> List[Tuple[Optional[str], str]]:
    """
    (key_id, secret) pairs from settings.WEBHOOK_SIGNING_KEYS, active key first.
    With nothing configured this returns an empty list, so verification fails
    closed. Only DEBUG gets a throwaway development key.
    """
    keys = _normalise_keys(getattr(settings, "WEBHOOK_SIGNING_KEYS", None) or [])
    if not keys and dev_fallback and getattr(settings, "DEBUG", False):
        keys = [("default_v1", DEV_FALLBACK_SECRET)]
    return keys


def _normalise_keys(secret: Any) -> List[Tuple[Optional[str], str]]:
    """Accept a str, a (key_id, secret) pair, or a list of either."""
    if isinstance(secret, str):
        items: List[Any] = [secret]
    elif (
        isinstance(secret, tuple)
        and len(secret) == 2
        and isinstance(secret[0], str)
        and isinstance(secret[1], str)
    ):
        items = [secret]
    elif isinstance(secret, (list, tuple)):
        items = list(secret)
    else:
        items = []

    keys: List[Tuple[Optional[str], str]] = []
    for item in items:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            key_id, sec = item
        else:
            key_id, sec = None, item
        if isinstance(sec, str) and sec:
            keys.append((key_id if isinstance(key_id, str) else None, sec))
    return keys


def _parse_timestamp(value: str) -> Optional[float]:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        return None
    return float(value)


def check_signature(
    secret: Any,
    payload: bytes,
    signature: Optional[str],
    *,
    timestamp: Optional[str] = None,
    key_id: Optional[str] = None,
    now: Optional[float] = None,
    tolerance: Optional[int] = None,
    require_timestamp: bool = False,
    allow_legacy: Optional[bool] = None,
) -> VerificationResult:
    """
    Verify a webhook signature and say why it was rejected.

    * ``timestamp`` is the raw header value. When present it must be a plain
      Unix timestamp within ``tolerance`` seconds of ``now`` (both directions),
      and the signature must cover ``"<timestamp>.<payload>"``.
    * ``require_timestamp`` rejects requests that carry no timestamp at all.
    * A payload-only (legacy) signature is accepted only if ``allow_legacy``
      (default: settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES). Its timestamp, if
      any, is not authenticated, so it gives no replay protection.
    * ``key_id`` is the key the sender says it used. Unknown ids are rejected;
      a known id restricts verification to that key.
    """
    if allow_legacy is None:
        allow_legacy = legacy_signatures_allowed()
    if tolerance is None:
        tolerance = get_timestamp_tolerance()
    claimed = key_id or None

    def reject(reason: str, **extra: Any) -> VerificationResult:
        return VerificationResult(
            False, reason, claimed_key_id=claimed, timestamp=timestamp, **extra
        )

    if not signature:
        return reject("missing_signature")
    if not isinstance(signature, str) or not _SIGNATURE_RE.fullmatch(signature):
        return reject("bad_signature_format")
    clean_sig = signature.removeprefix(SIGNATURE_PREFIX).encode("ascii")

    skew: Optional[float] = None
    if timestamp:
        ts_value = _parse_timestamp(timestamp)
        if ts_value is None:
            return reject("bad_timestamp")
        skew = (time.time() if now is None else now) - ts_value
        if skew > tolerance:
            return reject("stale_timestamp", skew_seconds=skew)
        if skew < -tolerance:
            return reject("future_timestamp", skew_seconds=skew)
    elif require_timestamp:
        return reject("missing_timestamp")

    # Deadlines are server-side absolute Unix times, never supplied by callers.
    # Check on every verification so long-running workers expire keys too.
    deadlines = getattr(settings, "WEBHOOK_SIGNING_KEY_EXPIRATIONS", {})
    verification_time = time.time() if now is None else now
    keys = []
    for kid, sec in _normalise_keys(secret):
        if kid in deadlines:
            deadline = deadlines[kid]
            if (
                isinstance(deadline, bool)
                or not isinstance(deadline, (int, float))
                or not math.isfinite(deadline)
                or verification_time >= deadline
            ):
                continue
        keys.append((kid, sec))
    if claimed is not None:
        keys = [k for k in keys if k[0] == claimed]
        if not keys:
            return reject("unknown_key_id", skew_seconds=skew)

    # Compare against every key and both formats without stopping at the first
    # hit, so timing does not reveal which key or format matched.
    bound_key: Optional[str] = None
    bound_hit = False
    legacy_key: Optional[str] = None
    legacy_hit = False
    for kid, sec in keys:
        if timestamp:
            expected = compute_signature(sec, payload, timestamp).encode("ascii")
            if hmac.compare_digest(expected, clean_sig) and not bound_hit:
                bound_hit, bound_key = True, kid
        expected = compute_signature(sec, payload).encode("ascii")
        if hmac.compare_digest(expected, clean_sig) and not legacy_hit:
            legacy_hit, legacy_key = True, kid

    if bound_hit:
        return VerificationResult(
            True,
            "ok",
            key_id=bound_key,
            skew_seconds=skew,
            claimed_key_id=claimed,
            timestamp=timestamp,
        )
    if legacy_hit:
        if allow_legacy:
            return VerificationResult(
                True,
                "legacy_signature",
                key_id=legacy_key,
                legacy=True,
                skew_seconds=skew,
                claimed_key_id=claimed,
                timestamp=timestamp,
            )
        return reject("legacy_signature_rejected", skew_seconds=skew)
    return reject("signature_mismatch", skew_seconds=skew)


def verify_signature(
    secret: Any,
    payload: bytes,
    signature: Optional[str],
    timestamp: Optional[str] = None,
    **kwargs: Any,
) -> bool:
    """
    Boolean form of ``check_signature``. Uses constant-time comparison.
    Supports secrets as strings, (key_id, secret) tuples, or lists of those.
    """
    return check_signature(secret, payload, signature, timestamp=timestamp, **kwargs).ok


def _log_safe(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _LOG_SAFE_RE.sub("?", str(value))[:64]


def audit_verification(
    result: VerificationResult, request: Any = None, source: str = ""
) -> None:
    """
    Structured audit line identifying the key used, or the rejection reason.

    Goes to the "audit" logger as one JSON object, like apps.cache.audit_logger.
    It never contains the secret, the signature or the body. Values that came
    from the sender are cut to 64 characters of [A-Za-z0-9_.:/-].

    A log line is used instead of an AuditEvent row on purpose: rejects come
    from unauthenticated callers, and one DB write per forged request would be
    a cheap way to fill the table.
    """
    meta = getattr(request, "META", {}) or {}
    entry = {
        "event": (
            (
                "webhook.legacy_signature_accepted"
                if result.legacy
                else "webhook.signature_accepted"
            )
            if result.ok
            else "webhook.signature_rejected"
        ),
        "reason": result.reason,
        "source": source,
        "path": _log_safe(getattr(request, "path", None)),
        "remote_addr": _log_safe(meta.get("REMOTE_ADDR")),
        "request_id": _log_safe(getattr(request, "request_id", None)),
        "key_id": _log_safe(result.key_id or result.claimed_key_id),
        "timestamp": _log_safe(result.timestamp),
        "skew_seconds": (
            None if result.skew_seconds is None else round(result.skew_seconds, 3)
        ),
    }
    log = audit_logger.info if result.ok and not result.legacy else audit_logger.warning
    log(json.dumps(entry))


_REJECTION_RESPONSES = {
    "missing_signature": 401,
    "missing_timestamp": 400,
    "bad_timestamp": 400,
    "stale_timestamp": 400,
    "future_timestamp": 400,
}
_TIMESTAMP_MESSAGES = {
    "missing_timestamp": "Missing X-Webhook-Timestamp header",
    "bad_timestamp": "Invalid X-Webhook-Timestamp header format",
    "stale_timestamp": "Webhook timestamp expired / out of window",
    "future_timestamp": "Webhook timestamp expired / out of window",
}


def rejection_response(result: VerificationResult, invalid_message: str):
    """(status, message) for a rejected result. Signature problems all share
    one generic 403 message so the response does not say which check failed."""
    status = _REJECTION_RESPONSES.get(result.reason, 403)
    message = _TIMESTAMP_MESSAGES.get(result.reason, invalid_message)
    return status, message


def require_webhook_signature(
    secret,
    header_name="HTTP_X_SIGNATURE",
    timestamp_header="HTTP_X_WEBHOOK_TIMESTAMP",
    key_id_header="HTTP_X_WEBHOOK_KEY_ID",
    require_timestamp=False,
):
    """
    View decorator to enforce HMAC signature verification on incoming webhooks.

    :param secret: A string or a callable that takes the `request` and returns a string secret or list of secrets.
    :param header_name: The Django META key for the header (e.g. 'HTTP_X_SIGNATURE' for 'X-Signature').
    :param timestamp_header: META key of the timestamp. If the request has one it is checked
        against the tolerance window and must be covered by the signature.
    :param require_timestamp: Reject requests without a timestamp header.
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
            result = check_signature(
                actual_secret,
                payload,
                signature,
                timestamp=request.META.get(timestamp_header),
                key_id=request.META.get(key_id_header),
                require_timestamp=require_timestamp,
            )
            audit_verification(result, request, source="require_webhook_signature")
            if not result.ok:
                status, message = rejection_response(result, "Invalid signature")
                return JsonResponse({"error": message}, status=status)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
