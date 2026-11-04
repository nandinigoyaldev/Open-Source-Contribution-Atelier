"""
Building blocks of the durable notification delivery ledger.

A delivery (one notification on one channel) is tracked by a ``NotificationDelivery`` row, and
every try at it is written to ``NotificationAttempt``. This module holds the parts the worker and
the channels share:

* ``DeliveryResult``: what a channel can return instead of a bare ``True``/``False``, carrying the
  provider's answer (status code, message id, response body) and whether a failure is worth retrying.
* ``DeliveryError``: what a channel raises when it knows the status code or the cause.
* ``classify_failure``: decides whether a failure is *transient* (try again later) or *permanent*
  (retrying cannot help, so go straight to the dead-letter table).
* ``make_dedupe_key``: a stable key for "the same event for the same recipient".
"""

import hashlib
import smtplib
from dataclasses import dataclass, field
from typing import Any, Optional

TRANSIENT = "transient"
PERMANENT = "permanent"
RATE_LIMITED = "rate_limited"

# Longest provider response body kept on a row; the ledger is for diagnosis, not archiving.
MAX_RESPONSE_CHARS = 1000
MAX_ERROR_CHARS = 2000

# HTTP statuses that mean "try again later" even though they are 4xx.
_RETRYABLE_HTTP = {408, 409, 423, 425, 429}


class DeliveryError(Exception):
    """A channel failure the channel can describe.

    ``retryable`` overrides the guess made from ``status_code``: ``True`` for transient,
    ``False`` for permanent, ``None`` to let :func:`classify_failure` decide.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        retryable: Optional[bool] = None,
        provider: str = "",
        response: Optional[dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.provider = provider
        self.response = response or {}


@dataclass
class DeliveryResult:
    """The outcome of one delivery attempt as reported by a channel."""

    success: bool = True
    provider: str = ""
    message_id: str = ""
    status_code: Optional[int] = None
    response: dict = field(default_factory=dict)
    error: str = ""
    retryable: Optional[bool] = None

    @classmethod
    def sent(cls, provider: str = "", **kwargs: Any) -> "DeliveryResult":
        return cls(success=True, provider=provider, **kwargs)

    @classmethod
    def permanent_failure(
        cls, error: str, provider: str = "", **kwargs: Any
    ) -> "DeliveryResult":
        """The notification can never be delivered (no address, no phone number...)."""
        return cls(
            success=False, error=error, provider=provider, retryable=False, **kwargs
        )

    @classmethod
    def transient_failure(
        cls, error: str, provider: str = "", **kwargs: Any
    ) -> "DeliveryResult":
        return cls(
            success=False, error=error, provider=provider, retryable=True, **kwargs
        )


def normalize_result(returned: Any) -> DeliveryResult:
    """Accept what older channels return (``True``/``False``/``None``) as well as a result."""
    if isinstance(returned, DeliveryResult):
        return returned
    if returned is True:
        return DeliveryResult.sent()
    # False (or None): the channel did not say why, so assume it might work next time.
    return DeliveryResult(
        success=False, error="Channel reported failure", retryable=True
    )


def _status_of(exc: BaseException) -> Optional[int]:
    """The HTTP-like status carried by an exception, whichever library raised it."""
    for attr in ("status_code", "status", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def classify_status(status: int) -> str:
    if status in _RETRYABLE_HTTP or status >= 500:
        return TRANSIENT
    if 400 <= status < 500:
        return PERMANENT
    return TRANSIENT


def classify_failure(exc: BaseException) -> str:
    """``"transient"`` or ``"permanent"`` for an exception raised while delivering."""
    explicit = getattr(exc, "retryable", None)
    if isinstance(explicit, bool):
        return TRANSIENT if explicit else PERMANENT

    status = _status_of(exc)
    if status is not None:
        return classify_status(status)

    # SMTP: 4xx replies are temporary, 5xx are permanent; refused recipients never get better.
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return PERMANENT
    if isinstance(exc, (smtplib.SMTPAuthenticationError, smtplib.SMTPSenderRefused)):
        return PERMANENT
    if isinstance(exc, smtplib.SMTPResponseException):
        # unlike HTTP, SMTP 4xx means "temporary failure, try again" and 5xx means "give up"
        return PERMANENT if 500 <= exc.smtp_code < 600 else TRANSIENT

    # Bad input from our own code will fail the same way again.
    if isinstance(
        exc, (ValueError, TypeError, LookupError, AttributeError, NotImplementedError)
    ):
        return PERMANENT

    # Network trouble, timeouts and anything unknown: worth another go, within the attempt limit.
    return TRANSIENT


def truncate(text: Any, limit: int) -> str:
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def backoff_seconds(attempt: int, base: int = 60, cap: int = 3600) -> int:
    """Wait before the next try: ``base``, ``2*base``, ``4*base``... up to ``cap``."""
    return min(cap, base * (2 ** max(0, attempt - 1)))


def make_dedupe_key(*parts: Any) -> str:
    """
    A stable key for an event, for ``dispatch_notification(..., dedupe_key=...)``.

    ``make_dedupe_key("badge", user.id, badge.id)`` is the same every time it is called with
    the same parts, so a retried signal handler or a re-delivered task cannot notify twice.
    """
    raw = "\x1f".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
