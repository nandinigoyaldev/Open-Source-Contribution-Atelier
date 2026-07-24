"""
Regex challenge lesson plugin.

Validates a user-submitted regular expression against a suite of test
strings (should-match / should-not-match), scoring by percentage of test
cases passed. Includes a timeout guard against catastrophic backtracking
(ReDoS) since the pattern being evaluated is arbitrary user input.
"""

import re
import signal
from typing import Any, Dict, List

from .plugins import LessonPlugin, registry


class RegexTimeoutError(Exception):
    """Raised when a regex match exceeds the allowed time budget."""


class _RegexWatchdog:
    """
    POSIX signal-based timeout guard for regex evaluation, to protect
    against catastrophic backtracking (ReDoS) from user-submitted patterns.

    Limitation: SIGALRM only works on POSIX systems and only in the main
    thread. If this plugin runs inside a worker/thread pool where SIGALRM
    isn't available, this guard is a no-op and falls through to running
    the regex unprotected — flagging this for review, since apps/sandbox
    already solves execution-safety for the Python sandbox lesson type and
    may have a subprocess-based pattern worth reusing here instead for a
    more robust cross-platform guard.
    """

    def __init__(self, timeout_seconds: float = 1.0):
        self.timeout_seconds = timeout_seconds
        self._supported = hasattr(signal, "SIGALRM")

    def __enter__(self):
        if self._supported:
            def _handler(signum, frame):
                raise RegexTimeoutError("Regex evaluation exceeded time limit")

            self._old_handler = signal.signal(signal.SIGALRM, _handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._supported:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self._old_handler)
        return False


def _compile_pattern(pattern: str, flags_str: str = "") -> "re.Pattern":
    """Compile a user-submitted pattern with only whitelisted flags."""
    flags = 0
    flag_map = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}
    for f in flags_str:
        if f not in flag_map:
            raise ValueError(f"Unsupported regex flag: {f}")
        flags |= flag_map[f]

    if len(pattern) > 500:
        raise ValueError("Pattern exceeds maximum allowed length (500 chars)")

    return re.compile(pattern, flags)


class RegexChallengePlugin(LessonPlugin):
    """
    Lesson plugin for regex-writing challenges.

    Expected submission data shape:
    {
        "pattern": "...",                 # user-submitted regex
        "flags": "im",                    # optional, subset of "ims"
        "test_cases": [                   # provided by the lesson definition,
            {"input": "abc123", "should_match": true},
            {"input": "xyz", "should_match": false},
            ...
        ]
    }
    """

    identifier = "regex_challenge"
    version = "1.0"
    name = "Regex Challenge"
    description = (
        "Write a regular expression that matches a given set of test "
        "strings and rejects another — scored by percentage of test "
        "cases passed, with a ReDoS timeout guard."
    )

    MAX_TEST_CASES = 100
    MATCH_TIMEOUT_SECONDS = 1.0

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        pattern = data.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return False

        flags = data.get("flags", "")
        if not isinstance(flags, str):
            return False

        test_cases = data.get("test_cases")
        if not isinstance(test_cases, list) or not test_cases:
            return False

        if len(test_cases) > cls.MAX_TEST_CASES:
            return False

        for case in test_cases:
            if not isinstance(case, dict):
                return False
            if "input" not in case or not isinstance(case["input"], str):
                return False
            if "should_match" not in case or not isinstance(case["should_match"], bool):
                return False

        try:
            _compile_pattern(pattern, flags)
        except (re.error, ValueError):
            return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        try:
            compiled = _compile_pattern(data["pattern"], data.get("flags", ""))
        except (re.error, ValueError):
            return 0.0

        test_cases: List[Dict[str, Any]] = data["test_cases"]
        passed = 0
        total = len(test_cases)

        for case in test_cases:
            try:
                with _RegexWatchdog(cls.MATCH_TIMEOUT_SECONDS):
                    is_match = compiled.search(case["input"]) is not None
            except RegexTimeoutError:
                # A pattern that times out on any single test case fails
                # that case outright (treated as a wrong/dangerous pattern).
                is_match = None

            if is_match is not None and is_match == case["should_match"]:
                passed += 1

        if total == 0:
            return 0.0

        return round((passed / total) * 100.0, 2)


registry.register(RegexChallengePlugin)
