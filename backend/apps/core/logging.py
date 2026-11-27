"""
Unified structured JSON logging and OpenTelemetry / X-Request-ID correlation pipeline.

Standard fields emitted in every JSON log entry:
- timestamp: ISO 8601 formatted UTC timestamp
- level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- trace_id: OpenTelemetry 32-character trace ID or incoming X-Request-ID / correlation ID
- span_id: OpenTelemetry 16-character span ID (if active)
- user_id: Authenticated user ID (or None)
- service: Service name identifier (from settings.SERVICE_NAME or OTEL_SERVICE_NAME)
- duration_ms: Request or execution duration in milliseconds (or None)
- message: Sanitized, PII-redacted log message

PII Redaction:
Automatically scrubs:
- Passwords and credentials
- Bearer tokens, JWTs, and API keys
- Credit card digits / PANs (13 to 19 digits)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import traceback
from typing import Any, Dict, Optional, Tuple, Union

from django.conf import settings

# Thread-local request correlation helpers
try:
    from apps.core.middleware.request_id import (
        get_correlation_id,
        get_request_id,
        get_user_id,
    )
except ImportError:

    def get_request_id():
        return None

    def get_correlation_id():
        return None

    def get_user_id():
        return None


# ==============================================================================
# PII Redaction Rules & Scrubbing
# ==============================================================================

PII_SCRUBBERS = [
    # 1. Passwords, secrets, credentials in key-value / JSON / query formats
    (
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|client_secret|private_key|token|access_token|refresh_token|api_key|auth_token)\b"
            r'(\s*[:=]\s*|\s+)(["\']?)(?P<val>[^\s"\'&,;}{]+)\3'
        ),
        r"\1\2\3[REDACTED]\3",
    ),
    # 2. Bearer tokens in Authorization headers / text
    (
        re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
        "Bearer [REDACTED]",
    ),
    # 3. JWTs (JSON Web Tokens: 3-part base64 strings starting with eyJ)
    (
        re.compile(r"\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+\b"),
        "[REDACTED_JWT]",
    ),
    # 4. Credit card digits (Primary Account Numbers): 13 to 19 digits
    (
        re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b|\b\d{13,19}\b"),
        "[REDACTED_CARD]",
    ),
]

SENSITIVE_KEY_NAMES = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "client_secret",
    "private_key",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "auth_token",
    "credit_card",
    "card_number",
    "cvv",
    "pan",
}


def redact_pii(data: Any) -> Any:
    """Recursively redacts passwords, tokens, and credit card digits from strings and collections."""
    if isinstance(data, str):
        text = data
        for pattern, replacement in PII_SCRUBBERS:
            text = pattern.sub(replacement, text)
        return text
    elif isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEY_NAMES:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_pii(v)
        return cleaned
    elif isinstance(data, (list, tuple)):
        return [redact_pii(item) for item in data]
    return data


class PIIRedactionFilter(logging.Filter):
    """
    Logging filter that sanitizes passwords, API keys/tokens, and credit card numbers
    from log records before emission.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Pre-format message if args exist to prevent format string injection issues
        if record.args:
            try:
                record.msg = record.msg % record.args
                record.args = ()
            except Exception:
                pass

        if isinstance(record.msg, str):
            record.msg = redact_pii(record.msg)

        if record.exc_info:
            try:
                exc_list = traceback.format_exception(*record.exc_info)
                record.exc_text = redact_pii("".join(exc_list))
            except Exception:
                pass
        elif getattr(record, "exc_text", None) and isinstance(record.exc_text, str):
            record.exc_text = redact_pii(record.exc_text)

        return True


# Backwards compatibility alias
SensitiveDataFilter = PIIRedactionFilter


# ==============================================================================
# Trace & Correlation Extraction
# ==============================================================================


def get_trace_correlation(
    record: Optional[logging.LogRecord] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts trace_id and span_id from OpenTelemetry active span or incoming X-Request-ID.
    Returns (trace_id, span_id).
    """
    trace_id = None
    span_id = None

    # 1. Check explicit attributes on record
    if record:
        rec_trace = getattr(record, "trace_id", None)
        rec_span = getattr(record, "span_id", None)
        if rec_trace and rec_trace != "-":
            return str(rec_trace), (
                str(rec_span) if rec_span and rec_span != "-" else None
            )

    # 2. Check OpenTelemetry active context
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None:
            ctx = span.get_span_context()
            if ctx is not None and ctx.is_valid:
                trace_id = f"{ctx.trace_id:032x}"
                span_id = f"{ctx.span_id:016x}"
                return trace_id, span_id
    except (ImportError, Exception):
        pass

    # 3. Fallback to incoming X-Request-ID or X-Correlation-ID from request middleware
    req_id = get_request_id() or get_correlation_id()
    if req_id and req_id != "-":
        return str(req_id), None

    return None, None


# ==============================================================================
# Unified Structured JSON Formatter
# ==============================================================================

STANDARD_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
    "request_id",
    "correlation_id",
    "user_id",
    "trace_id",
    "span_id",
    "duration_ms",
    "service",
}


class StructuredJsonFormatter(logging.Formatter):
    """
    Unified structured JSON log formatter.

    Outputs JSON entries containing the standard fields:
    - timestamp (ISO 8601 UTC)
    - level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - trace_id (OpenTelemetry trace_id or X-Request-ID)
    - span_id (OpenTelemetry span_id if available)
    - user_id (Authenticated user ID or None)
    - service (Service identifier)
    - duration_ms (Execution duration in milliseconds if available)
    - message (PII-redacted message string)
    """

    def __init__(self, service_name: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = (
            service_name
            or os.getenv("OTEL_SERVICE_NAME")
            or getattr(settings, "SERVICE_NAME", "atelier-backend")
        )

    def format(self, record: logging.LogRecord) -> str:
        # Pre-format message if args exist
        if record.args:
            try:
                record.msg = record.msg % record.args
                record.args = ()
            except Exception:
                pass

        message_str = (
            record.getMessage() if hasattr(record, "getMessage") else str(record.msg)
        )
        sanitized_message = redact_pii(message_str)

        trace_id, span_id = get_trace_correlation(record)

        # Extract user_id
        user_id = getattr(record, "user_id", None)
        if not user_id or user_id == "-":
            user_id = get_user_id()
        if user_id == "-":
            user_id = None
        if user_id is not None:
            user_id = str(user_id)

        # Extract duration_ms
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is None:
            try:
                from apps.core.middleware.request_id import _thread_locals

                duration_ms = getattr(_thread_locals, "duration_ms", None)
            except Exception:
                duration_ms = None

        if duration_ms is not None:
            try:
                duration_ms = round(float(duration_ms), 2)
            except (ValueError, TypeError):
                duration_ms = None

        # Build ISO-8601 UTC timestamp
        timestamp = datetime.datetime.fromtimestamp(
            record.created, tz=datetime.timezone.utc
        ).isoformat()

        # Build standard log dictionary
        log_entry: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "trace_id": trace_id,
            "span_id": span_id,
            "user_id": user_id,
            "service": self.service_name,
            "duration_ms": duration_ms,
            "message": sanitized_message,
            "logger": record.name,
        }

        # Include exception info if present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_entry["exception"] = redact_pii(record.exc_text)

        # Collect any extra contextual fields attached to the LogRecord
        extra = {}
        for key, value in record.__dict__.items():
            if key not in STANDARD_RECORD_ATTRS and not key.startswith("_"):
                extra[key] = redact_pii(value)

        if extra:
            log_entry["extra"] = extra

        return json.dumps(log_entry, default=str)
