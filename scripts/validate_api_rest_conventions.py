#!/usr/bin/env python3
"""Validate REST API endpoint naming, casing, and URL path conventions.

Scans backend routing files (Express, Flask, FastAPI) and flags REST design anti-patterns
such as non-kebab/camelCase path segments, redundant CRUD action verbs embedded in URLs,
trailing slashes, and inconsistent route parameters.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

# Common CRUD verbs that should be represented via HTTP methods (GET, POST, PUT, DELETE, PATCH)
# rather than in the URI path itself.
FORBIDDEN_PATH_VERBS = {
    "get",
    "create",
    "add",
    "insert",
    "update",
    "edit",
    "modify",
    "delete",
    "remove",
    "destroy",
    "fetch",
    "list",
}

# Regex to detect route declarations across JavaScript/TypeScript & Python frameworks:
# e.g.: router.get('/users/:id', ...), app.post("/api/items", ...)
EXPRESS_ROUTE_REGEX = re.compile(
    r"\b(?:app|router|server)\.(?P<method>get|post|put|delete|patch|options|head)\s*\(\s*['\"](?P<path>/[^'\"]*)['\"]",
    re.IGNORECASE,
)

# e.g.: @app.get('/users/{id}'), @router.post("/items")
PYTHON_ROUTE_REGEX = re.compile(
    r"@(?:app|router|blueprint|bp)\.(?P<method>get|post|put|delete|patch)\s*\(\s*['\"](?P<path>/[^'\"]*)['\"]",
    re.IGNORECASE,
)

SUPPORTED_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".py"}

IGNORE_DIRS = {
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".cache",
}


def is_parameter_segment(segment: str) -> bool:
    """Check if segment is a path parameter like :id, :userId, {id}, {user_id}."""
    return (segment.startswith(":") and len(segment) > 1) or (
        segment.startswith("{") and segment.endswith("}")
    )


def validate_path_conventions(
    path: str,
    method: str,
    file_path: str,
    line_no: int,
    forbidden_verbs: set[str],
) -> List[Dict[str, Any]]:
    """Validate a single endpoint path for RESTful conventions."""
    findings: List[Dict[str, Any]] = []

    # Check 1: Trailing slash check (ignore single '/' or root api endpoints)
    if len(path) > 1 and path.endswith("/"):
        findings.append({
            "file": file_path,
            "line": line_no,
            "method": method.upper(),
            "path": path,
            "type": "TRAILING_SLASH",
            "severity": "WARNING",
            "message": f"Endpoint '{method.upper()} {path}' has a trailing slash. REST endpoints should omit trailing slashes.",
        })

    # Strip leading/trailing slashes for segment parsing
    trimmed_path = path.strip("/")
    if not trimmed_path:
        return findings

    segments = trimmed_path.split("/")

    for seg in segments:
        if not seg:
            continue

        if is_parameter_segment(seg):
            # Parameter formatting check
            param_name = seg[1:] if seg.startswith(":") else seg[1:-1]
            if not re.match(r"^[a-zA-Z0-9_\-]+$", param_name):
                findings.append({
                    "file": file_path,
                    "line": line_no,
                    "method": method.upper(),
                    "path": path,
                    "type": "INVALID_PARAM_FORMAT",
                    "severity": "ERROR",
                    "message": f"Parameter '{seg}' in endpoint '{path}' contains invalid characters.",
                })
            continue

        # Check 2: Casing conventions (must be lowercase kebab-case or snake_case, no uppercase/camelCase)
        if any(c.isupper() for c in seg):
            findings.append({
                "file": file_path,
                "line": line_no,
                "method": method.upper(),
                "path": path,
                "type": "CAMELCASE_PATH_SEGMENT",
                "severity": "WARNING",
                "message": f"Path segment '{seg}' contains uppercase characters. Use kebab-case instead.",
            })

        # Check 3: Redundant CRUD verbs in URL
        # Convert camelCase and kebab/snake into individual lowercased word tokens
        de_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", seg)
        words = [w.lower() for w in re.split(r"[-_]+", de_camel) if w]
        for w in words:
            if w in forbidden_verbs:
                findings.append({
                    "file": file_path,
                    "line": line_no,
                    "method": method.upper(),
                    "path": path,
                    "type": "VERB_IN_ENDPOINT_PATH",
                    "severity": "WARNING",
                    "message": f"Endpoint contains action verb '{w}'. Use HTTP method {method.upper()} with noun resources instead.",
                })
                break

    return findings


class RestConventionValidator:
    """Validator for REST endpoint conventions across codebase files."""

    def __init__(self, forbidden_verbs: Optional[set[str]] = None):
        self.forbidden_verbs = (
            {v.lower() for v in forbidden_verbs}
            if forbidden_verbs is not None
            else FORBIDDEN_PATH_VERBS
        )

    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f, start=1):
                    # Check Express pattern
                    for match in EXPRESS_ROUTE_REGEX.finditer(line):
                        method = match.group("method")
                        path = match.group("path")
                        findings.extend(
                            validate_path_conventions(
                                path, method, str(file_path), line_idx, self.forbidden_verbs
                            )
                        )

                    # Check Python pattern
                    for match in PYTHON_ROUTE_REGEX.finditer(line):
                        method = match.group("method")
                        path = match.group("path")
                        findings.extend(
                            validate_path_conventions(
                                path, method, str(file_path), line_idx, self.forbidden_verbs
                            )
                        )
        except Exception:
            pass
        return findings

    def scan_directory(self, root_path: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    file_path = Path(root) / file
                    findings.extend(self.scan_file(file_path))

        return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate REST API endpoint naming and casing conventions."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root path to scan (default: current directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with non-zero code on warnings.",
    )

    args = parser.parse_args()
    validator = RestConventionValidator()
    findings = validator.scan_directory(args.root)

    errors = [f for f in findings if f.get("severity") == "ERROR"]
    warnings = [f for f in findings if f.get("severity") == "WARNING"]

    if args.json:
        print(json.dumps({
            "total_findings": len(findings),
            "errors": len(errors),
            "warnings": len(warnings),
            "findings": findings,
        }, indent=2))
    else:
        print(f"REST API Convention Audit for {args.root.resolve()}")
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}\n")

        for f in findings:
            prefix = "[ERROR]" if f.get("severity") == "ERROR" else "[WARNING]"
            print(f"{prefix} [{f['type']}] {f['file']}:{f['line']} -> {f['message']}")

    if errors:
        return 1
    if warnings and args.fail_on_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
