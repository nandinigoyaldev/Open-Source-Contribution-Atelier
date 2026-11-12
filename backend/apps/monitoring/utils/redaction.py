import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|token|secret|api[_-]?key|auth|credential|private|bearer|session|cookie|credit[_-]?card)",
    re.IGNORECASE,
)

REDACTED_STR = "[REDACTED]"


def redact_data(data: Any) -> Any:
    """
    Recursively sanitize dictionaries, lists, and tuples to redact sensitive fields.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, val in data.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                sanitized[key] = REDACTED_STR
            else:
                sanitized[key] = redact_data(val)
        return sanitized
    elif isinstance(data, list):
        return [redact_data(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(redact_data(item) for item in data)
    return data


def format_redacted_args(
    args: Any = None, kwargs: Any = None, max_length: int = 1000
) -> str:
    """
    Redact args and kwargs and return safe string summary representation.
    """
    redacted_args = redact_data(args) if args else ()
    redacted_kwargs = redact_data(kwargs) if kwargs else {}

    parts = []
    if redacted_args:
        parts.append(f"args={redacted_args}")
    if redacted_kwargs:
        parts.append(f"kwargs={redacted_kwargs}")

    summary = ", ".join(parts)
    if len(summary) > max_length:
        return summary[: max_length - 3] + "..."
    return summary
