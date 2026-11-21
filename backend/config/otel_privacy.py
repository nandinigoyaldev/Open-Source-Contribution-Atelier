"""
Scrubbing helpers for trace data.

Plain functions with no OpenTelemetry import, so the request middleware can use them even when
the SDK is missing. ``config.otel_pipeline.ScrubbingSpanExporter`` runs every finished span
through ``scrub_attributes`` before export, and the DB/cache/HTTP spans in
``config.otel_instrumentation`` only record already scrubbed values in the first place.

Rules:
- attribute keys that name a secret (password, token, cookie, authorization, api key, ...)
  keep the key but lose the value,
- client IP and user agent attributes are dropped,
- URLs lose user info, every query value and path segments that look like tokens or emails,
- SQL loses string and number literals (parameters are never recorded at all),
- any other string goes through the same masking as the log filter (emails, JWTs,
  ``token=...`` style pairs).
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from config.logging_filters import SensitiveDataFilter

REDACTED = "[REDACTED]"

MAX_STATEMENT_LENGTH = 1000

_mask_text = SensitiveDataFilter().mask_text

_SENSITIVE_KEY = re.compile(
    r"passw|secret|token|authorization|cookie|api[-_.]?key|session|csrf|"
    r"credential|private[-_.]?key|signature|otp",
    re.IGNORECASE,
)

# Personal data about the caller; not needed to follow a trace.
_DROPPED_KEYS = frozenset(
    {
        "client.address",
        "http.client_ip",
        "net.peer.ip",
        "net.sock.peer.addr",
        "network.peer.address",
        "http.user_agent",
        "user_agent.original",
    }
)

_URL_KEYS = frozenset({"http.url", "url.full", "http.target", "url.path"})
_QUERY_KEYS = frozenset({"url.query"})
_SQL_KEYS = frozenset({"db.statement", "db.query.text"})

_SQL_STRING = re.compile(r"'(?:[^']|'')*'")
_SQL_NUMBER = re.compile(r"(?<![\w\"$.])\d+(?:\.\d+)?\b")
_HAS_DIGIT = re.compile(r"\d")
_HAS_LETTER = re.compile(r"[A-Za-z]")
_KEY_PREFIX = re.compile(r"[a-z][a-z0-9_.-]{0,31}")


def scrub_text(value: str) -> str:
    """Mask emails, JWTs and ``token=...`` style secrets inside free text."""
    return _mask_text(value)


def _looks_secret(segment: str) -> bool:
    decoded = unquote(segment)
    if "@" in decoded:
        return True
    return (
        len(decoded) >= 16
        and bool(_HAS_DIGIT.search(decoded))
        and bool(_HAS_LETTER.search(decoded))
    )


def scrub_path(path: str) -> str:
    """Replace path segments that look like tokens, ids or emails."""
    return "/".join(
        REDACTED if segment and _looks_secret(segment) else segment
        for segment in path.split("/")
    )


def scrub_query(query: str) -> str:
    """Keep query parameter names, drop every value."""
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    return "&".join(f"{scrub_text(key)}={REDACTED}" for key, _ in pairs)


def scrub_url(url: str) -> str:
    """Return ``url`` without user info, query values, fragment or token-like path segments."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return REDACTED
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port else host
    return urlunsplit(
        (parts.scheme, netloc, scrub_path(parts.path), scrub_query(parts.query), "")
    )


def scrub_sql(statement: str) -> str:
    """Strip literals from a SQL statement and cap its length."""
    cleaned = _SQL_STRING.sub("?", statement)
    cleaned = _SQL_NUMBER.sub("?", cleaned)
    cleaned = scrub_text(cleaned)
    if len(cleaned) > MAX_STATEMENT_LENGTH:
        cleaned = cleaned[:MAX_STATEMENT_LENGTH] + "..."
    return cleaned


def cache_key_prefix(key: str) -> str | None:
    """
    Return the namespace of a cache key (``"ratelimit"`` for ``"ratelimit:42:login"``).

    Full keys often hold user ids, emails or tokens, so only a short lowercase prefix is kept,
    and only when it looks like a plain name.
    """
    head = key.split(":", 1)[0]
    if head != key and _KEY_PREFIX.fullmatch(head):
        return head
    return None


def _scrub_value(key: str, value: Any) -> Any:
    if isinstance(value, str):
        if key in _URL_KEYS:
            return scrub_url(value)
        if key in _QUERY_KEYS:
            return scrub_query(value)
        if key in _SQL_KEYS:
            return scrub_sql(value)
        return scrub_text(value)
    if isinstance(value, (list, tuple)):
        return tuple(scrub_text(v) if isinstance(v, str) else v for v in value)
    return value


def scrub_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a scrubbed copy of a span/event attribute mapping."""
    cleaned: dict[str, Any] = {}
    for key, value in (attributes or {}).items():
        if key in _DROPPED_KEYS:
            continue
        if _SENSITIVE_KEY.search(key):
            cleaned[key] = REDACTED
            continue
        cleaned[key] = _scrub_value(key, value)
    return cleaned
