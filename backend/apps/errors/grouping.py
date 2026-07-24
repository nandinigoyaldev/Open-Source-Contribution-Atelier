import re
import hashlib

# Regular expressions for identifying dynamic content
IPV4_PATTERN = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
IPV6_PATTERN = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{1,4}\b")
UUID_PATTERN = re.compile(
    r"\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b"
)
EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
USER_ID_PATTERN = re.compile(
    r"\b(user[_-]?id\b[=:\s]*\d+|\buser\s+#?\d+|\buser/\d+)\b", re.IGNORECASE
)


def normalize_message(message: str) -> str:
    """
    Normalizes error messages by replacing dynamic values with placeholders.
    This ensures that errors differing only by user IDs, IPs, UUIDs, emails,
    or timestamps are grouped together.
    """
    if not message:
        return ""

    # Normalize IP addresses
    message = IPV4_PATTERN.sub("<IP>", message)
    message = IPV6_PATTERN.sub("<IP>", message)

    # Normalize UUIDs
    message = UUID_PATTERN.sub("<UUID>", message)

    # Normalize Email addresses
    message = EMAIL_PATTERN.sub("<EMAIL>", message)

    # Normalize Timestamps
    message = TIMESTAMP_PATTERN.sub("<TIMESTAMP>", message)

    # Normalize User IDs
    message = USER_ID_PATTERN.sub("<USER_ID>", message)

    return message


def get_stacktrace_fingerprint(stacktrace: str) -> str:
    """
    Cleans up stacktrace to create a reliable signature:
    - Strips line numbers (which shift as files edit).
    - Normalizes path names and separators.
    """
    if not stacktrace:
        return ""

    # Remove line numbers (e.g. ", line 123" or "line 123")
    st = re.sub(r"\bline \d+\b", "", stacktrace)
    st = re.sub(r", line \d+", "", st)

    # Normalize directory paths and separators
    st = st.replace("\\", "/")

    return st.strip()


def calculate_fingerprint(normalized_message: str, stacktrace: str, module: str) -> str:
    """
    Computes a unique SHA256 grouping key.
    """
    st_fp = get_stacktrace_fingerprint(stacktrace)
    raw_key = f"{normalized_message}|{st_fp}|{module}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
