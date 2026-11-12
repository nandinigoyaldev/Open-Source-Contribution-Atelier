#!/usr/bin/env python3
"""Automated TODO and FIXME annotation tracker with date expiration audit.

Scans the codebase for inline technical debt markers (TODO, FIXME, HACK, XXX, BUG),
extracts assigned owners, linked issues, and expiration deadlines, and validates
whether temporary debt items have exceeded their scheduled remediation date.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_TAGS = {"TODO", "FIXME", "HACK", "XXX", "BUG"}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".sh",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".css",
    ".scss",
    ".html",
}

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

# Regex to capture: TAG (optional (details)): message
# e.g.: TODO: fix this
#       TODO(harshit, 2026-03-01): refactor
#       FIXME(#123): handle edge case
#       HACK(2025-01-01): temporary workaround
ANNOTATION_REGEX = re.compile(
    r"\b(?P<tag>TODO|FIXME|HACK|XXX|BUG)\b(?:\((?P<metadata>[^)]+)\))?\s*[:\-]?\s*(?P<message>.*)$",
    re.IGNORECASE,
)

DATE_REGEX = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
ISSUE_REGEX = re.compile(r"#(\d+)")


def parse_metadata(metadata_str: Optional[str]) -> Tuple[Optional[str], Optional[datetime.date], Optional[str]]:
    """Parse metadata string into (author, date, issue)."""
    if not metadata_str:
        return None, None, None

    metadata_str = metadata_str.strip()
    date_val: Optional[datetime.date] = None
    issue_val: Optional[str] = None
    author_val: Optional[str] = None

    date_match = DATE_REGEX.search(metadata_str)
    if date_match:
        try:
            date_val = datetime.date.fromisoformat(date_match.group(1))
        except ValueError:
            pass

    issue_match = ISSUE_REGEX.search(metadata_str)
    if issue_match:
        issue_val = f"#{issue_match.group(1)}"

    # Remaining parts could be the author
    parts = [p.strip() for p in metadata_str.split(",") if p.strip()]
    for p in parts:
        if not DATE_REGEX.search(p) and not ISSUE_REGEX.search(p):
            author_val = p
            break

    return author_val, date_val, issue_val


def parse_line_annotation(
    line: str, line_no: int, file_path: str, reference_date: datetime.date
) -> Optional[Dict[str, Any]]:
    """Analyze a single line for annotations."""
    match = ANNOTATION_REGEX.search(line)
    if not match:
        return None

    raw_tag = match.group("tag").upper()
    metadata = match.group("metadata")
    message = match.group("message").strip()

    # Clean comment closing tokens (e.g., '*/', '-->')
    message = re.sub(r"(\*/|-->)$", "", message).strip()

    author, deadline, issue = parse_metadata(metadata)

    is_expired = False
    days_overdue = 0
    if deadline:
        if deadline < reference_date:
            is_expired = True
            days_overdue = (reference_date - deadline).days

    return {
        "file": file_path,
        "line": line_no,
        "tag": raw_tag,
        "raw_metadata": metadata,
        "author": author,
        "issue": issue,
        "deadline": deadline.isoformat() if deadline else None,
        "is_expired": is_expired,
        "days_overdue": days_overdue,
        "message": message,
    }


class TodoTracker:
    """Scans and audits TODO/FIXME annotations in codebase."""

    def __init__(self, reference_date: Optional[datetime.date] = None):
        self.reference_date = reference_date or datetime.date.today()

    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan a single file for annotations."""
        findings: List[Dict[str, Any]] = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f, start=1):
                    parsed = parse_line_annotation(
                        line, idx, str(file_path), self.reference_date
                    )
                    if parsed:
                        findings.append(parsed)
        except Exception:
            pass
        return findings

    def scan_directory(self, root_path: Path) -> List[Dict[str, Any]]:
        """Walk root_path and collect all annotations."""
        all_findings: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    file_path = Path(root) / file
                    all_findings.extend(self.scan_file(file_path))

        return all_findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan codebase for TODO/FIXME annotations and audit expiration dates."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root path to scan (default: current directory).",
    )
    parser.add_argument(
        "--ref-date",
        type=str,
        default=None,
        help="Reference ISO date YYYY-MM-DD for expiration comparison (default: today).",
    )
    parser.add_argument(
        "--fail-on-expired",
        action="store_true",
        help="Exit with code 1 if any expired TODO/FIXME is found.",
    )
    parser.add_argument(
        "--fail-on-unassigned",
        action="store_true",
        help="Exit with code 1 if any annotation lacks author or issue metadata.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )

    args = parser.parse_args()

    ref_date = (
        datetime.date.fromisoformat(args.ref_date)
        if args.ref_date
        else datetime.date.today()
    )

    tracker = TodoTracker(reference_date=ref_date)
    findings = tracker.scan_directory(args.root)

    expired = [f for f in findings if f.get("is_expired")]
    unassigned = [f for f in findings if not f.get("author") and not f.get("issue")]

    if args.json:
        print(json.dumps({
            "reference_date": ref_date.isoformat(),
            "total_annotations": len(findings),
            "expired_count": len(expired),
            "unassigned_count": len(unassigned),
            "findings": findings,
        }, indent=2))
    else:
        print(f"Annotation Tracker Audit (Reference Date: {ref_date})")
        print(f"Total: {len(findings)}, Expired: {len(expired)}, Unassigned: {len(unassigned)}\n")

        for f in findings:
            status = "[EXPIRED]" if f.get("is_expired") else "[ACTIVE]"
            meta = f" ({f.get('raw_metadata')})" if f.get("raw_metadata") else ""
            print(f"{status} {f['tag']}{meta} at {f['file']}:{f['line']} -> {f['message']}")

    if args.fail_on_expired and expired:
        return 1
    if args.fail_on_unassigned and unassigned:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
