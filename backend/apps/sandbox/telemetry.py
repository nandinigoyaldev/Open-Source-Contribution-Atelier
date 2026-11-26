"""
Privacy-safe telemetry metrics for sandbox output truncation.

Emits counters for output truncation events, categorizing by stream (stdout vs stderr),
command category (e.g., git subcommand, python), and the configured byte/character limit.

Privacy guarantee:
Learner output content, code, commands with arguments, secrets, and environment tokens
are NEVER logged or included in metrics. Only sanitized metadata (stream, category, limit)
is recorded.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter as _PyCounter
from typing import Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

TRUNCATION_COUNTER_NAME = "sandbox_output_truncation_total"

# Standard default limit (64KB) matching ResourceManagementEngine.MAX_OUTPUT_BYTES
DEFAULT_OUTPUT_LIMIT = 64 * 1024

try:
    from prometheus_client import REGISTRY, Counter

    OUTPUT_TRUNCATION_COUNTER = Counter(
        TRUNCATION_COUNTER_NAME,
        "Total count of sandbox output truncation events by stream, command category, and limit.",
        ["stream", "command_category", "limit"],
    )
except (ImportError, ValueError):
    # Duplicate registration during test discovery / importlib or prometheus_client not available
    OUTPUT_TRUNCATION_COUNTER = None

_lock = threading.Lock()
# In-process counter storing (stream, command_category, limit) -> count
_counts: _PyCounter[Tuple[str, str, str]] = _PyCounter()

# Known Git subcommands from allowlist and standard git CLI
KNOWN_GIT_SUBCOMMANDS = {
    "status",
    "init",
    "add",
    "commit",
    "branch",
    "checkout",
    "switch",
    "merge",
    "rebase",
    "log",
    "pull",
    "push",
    "clone",
    "diff",
    "remote",
    "fetch",
    "reset",
    "stash",
    "tag",
    "show",
    "cherry-pick",
}


def categorize_command(command: Optional[str]) -> str:
    """
    Extracts a privacy-safe high-level command category from a command string.

    Never extracts or returns arguments, flags, messages, paths, or user data.
    Returns:
        e.g., 'commit', 'checkout', 'status', 'add', 'merge', 'rebase',
              'python', 'git', or 'unknown'.
    """
    if not command or not isinstance(command, str):
        return "unknown"

    stripped = command.strip()
    if not stripped:
        return "unknown"

    # Normalize tokens without evaluating flags or arguments
    tokens = stripped.split()
    first_token = tokens[0].lower() if tokens else ""

    if first_token == "git":
        if len(tokens) > 1:
            sub = tokens[1].lower()
            # Strip any punctuation or characters like quotes
            sub_clean = re.sub(r"[^a-z0-9\-]", "", sub)
            if sub_clean in KNOWN_GIT_SUBCOMMANDS:
                return sub_clean
            if sub_clean.startswith("-"):
                return "git"
            return sub_clean or "git"
        return "git"

    if first_token in ("python", "python3", "py"):
        return "python"

    if first_token in KNOWN_GIT_SUBCOMMANDS:
        return first_token

    if first_token in ("bash", "sh", "zsh", "shell"):
        return "shell"

    if first_token.startswith("git-"):
        return first_token[4:]

    return "unknown"


def record_output_truncation(
    stream: str,
    command_category: str,
    limit: Union[int, str],
) -> None:
    """
    Emits a privacy-safe metric counter increment for an output truncation event.

    Args:
        stream: 'stdout' or 'stderr'
        command_category: e.g. 'commit', 'status', 'python', 'unknown'
        limit: configured maximum byte or character threshold
    """
    stream_norm = "stderr" if str(stream).lower().strip() == "stderr" else "stdout"
    cat_norm = str(command_category).strip().lower() or "unknown"
    limit_str = str(limit)

    key = (stream_norm, cat_norm, limit_str)

    with _lock:
        _counts[key] += 1

    if OUTPUT_TRUNCATION_COUNTER is not None:
        try:
            OUTPUT_TRUNCATION_COUNTER.labels(
                stream=stream_norm,
                command_category=cat_norm,
                limit=limit_str,
            ).inc()
        except Exception as exc:
            logger.debug("Failed to increment prometheus truncation counter: %s", exc)

    # Privacy-safe log: ONLY stream, category, limit. NEVER learner output or secrets!
    logger.info(
        "Sandbox output truncated: stream=%s command_category=%s limit=%s",
        stream_norm,
        cat_norm,
        limit_str,
    )


def truncate_sandbox_output(
    output: Union[str, bytes],
    stream: str = "stdout",
    command: Optional[str] = None,
    command_category: Optional[str] = None,
    limit: Optional[int] = None,
) -> Tuple[Union[str, bytes], bool]:
    """
    Enforces the configured output limit on stdout or stderr. If output exceeds
    the limit, it is truncated and a privacy-safe telemetry counter is emitted.

    Args:
        output: output string or bytes
        stream: 'stdout' or 'stderr'
        command: optional command string to infer category if command_category is omitted
        command_category: explicit command category (e.g., 'commit', 'python')
        limit: maximum allowed length (defaults to DEFAULT_OUTPUT_LIMIT)

    Returns:
        (truncated_output, was_truncated)
    """
    if output is None:
        return ("", False)

    effective_limit = limit if limit is not None else DEFAULT_OUTPUT_LIMIT

    current_length = len(output)

    if current_length > effective_limit:
        truncated = output[:effective_limit]
        cat = command_category or categorize_command(command)
        record_output_truncation(
            stream=stream,
            command_category=cat,
            limit=effective_limit,
        )
        return (truncated, True)

    return (output, False)


def get_truncation_count(
    stream: str,
    command_category: str,
    limit: Union[int, str],
) -> int:
    """Returns the in-process count for a given stream, category, and limit (used in tests)."""
    stream_norm = "stderr" if str(stream).lower().strip() == "stderr" else "stdout"
    cat_norm = str(command_category).strip().lower() or "unknown"
    limit_str = str(limit)
    with _lock:
        return _counts.get((stream_norm, cat_norm, limit_str), 0)


def get_all_truncation_counts() -> dict[Tuple[str, str, str], int]:
    """Returns a copy of all in-process truncation counts."""
    with _lock:
        return dict(_counts)


def reset_telemetry() -> None:
    """Clears in-process counts (used in test tearDown)."""
    with _lock:
        _counts.clear()
