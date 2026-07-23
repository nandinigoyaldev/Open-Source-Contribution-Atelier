"""
API request challenge lesson plugin.

Validates a user-submitted HTTP request specification (method, path,
headers, JSON body) against an expected request shape. No actual HTTP
request is ever made — this is a pure structural comparison, kept
intentionally side-effect-free for safety since the input is arbitrary
user submission.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .plugins import LessonPlugin, registry


def _path_matches(submitted_path: str, expected_path: str) -> bool:
    """
    Compare paths, treating {param}-style segments in expected_path as
    wildcards that match any non-empty segment in submitted_path.
    e.g. expected "/users/{id}/posts" matches submitted "/users/42/posts".
    """
    submitted_segments = [s for s in submitted_path.strip("/").split("/") if s != ""]
    expected_segments = [s for s in expected_path.strip("/").split("/") if s != ""]

    if len(submitted_segments) != len(expected_segments):
        return False

    for sub_seg, exp_seg in zip(submitted_segments, expected_segments):
        if exp_seg.startswith("{") and exp_seg.endswith("}"):
            if not sub_seg:
                return False
        elif sub_seg != exp_seg:
            return False

    return True


def _headers_match(submitted_headers: Dict[str, str], required_headers: Dict[str, str]) -> Tuple[int, int]:
    """Case-insensitive header key/value comparison. Returns (matched_count, required_count)."""
    normalized_submitted = {k.lower(): v for k, v in submitted_headers.items()}
    matched = 0
    for key, expected_value in required_headers.items():
        actual_value = normalized_submitted.get(key.lower())
        if actual_value is not None and actual_value.strip() == expected_value.strip():
            matched += 1
    return matched, len(required_headers)


def _json_bodies_structurally_equal(a: Any, b: Any) -> bool:
    """Deep structural equality for parsed JSON values (dict/list/scalar)."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_json_bodies_structurally_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_json_bodies_structurally_equal(x, y) for x, y in zip(a, b))
    return a == b


class APIRequestChallengePlugin(LessonPlugin):
    """
    Lesson plugin for "construct the correct HTTP request" challenges.
    No network calls are made — pure structural comparison against an
    expected request specification.

    Expected submission data shape:
    {
        "submitted": {
            "method": "POST",
            "path": "/users/42/posts",
            "headers": {"Content-Type": "application/json"},
            "body": "{\\"title\\": \\"Hello\\"}"
        },
        "expected": {
            "method": "POST",
            "path": "/users/{id}/posts",
            "required_headers": {"Content-Type": "application/json"},
            "body": {"title": "Hello"}
        }
    }
    """

    identifier = "api_request_challenge"
    version = "1.0"
    name = "API Request Challenge"
    description = (
        "Construct an HTTP request (method, path, headers, JSON body) "
        "matching an expected specification. No network call is made — "
        "purely structural comparison."
    )

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        submitted = data.get("submitted")
        expected = data.get("expected")

        if not isinstance(submitted, dict) or not isinstance(expected, dict):
            return False

        if not isinstance(submitted.get("method"), str) or not isinstance(expected.get("method"), str):
            return False

        if not isinstance(submitted.get("path"), str) or not isinstance(expected.get("path"), str):
            return False

        if "headers" in submitted and not isinstance(submitted["headers"], dict):
            return False

        if "required_headers" in expected and not isinstance(expected["required_headers"], dict):
            return False

        if "body" in submitted:
            if not isinstance(submitted["body"], str):
                return False
            try:
                json.loads(submitted["body"])
            except json.JSONDecodeError:
                return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        submitted = data["submitted"]
        expected = data["expected"]

        checks_passed = 0
        checks_total = 0

        # Method check (case-insensitive)
        checks_total += 1
        if submitted["method"].strip().upper() == expected["method"].strip().upper():
            checks_passed += 1

        # Path check (with {param} wildcard support)
        checks_total += 1
        if _path_matches(submitted["path"], expected["path"]):
            checks_passed += 1

        # Headers check
        required_headers = expected.get("required_headers", {})
        if required_headers:
            matched, required_count = _headers_match(submitted.get("headers", {}), required_headers)
            checks_total += required_count
            checks_passed += matched

        # Body check
        if "body" in expected:
            checks_total += 1
            expected_body = expected["body"]
            submitted_body_raw = submitted.get("body")
            if submitted_body_raw is not None:
                try:
                    submitted_body = json.loads(submitted_body_raw)
                    if _json_bodies_structurally_equal(submitted_body, expected_body):
                        checks_passed += 1
                except json.JSONDecodeError:
                    pass

        if checks_total == 0:
            return 0.0

        return round((checks_passed / checks_total) * 100.0, 2)


registry.register(APIRequestChallengePlugin)
