#!/usr/bin/env python3
"""Audit i18n localization translation strings for unsafe HTML markup and XSS vectors.

Scans translation dictionary files (JSON) to detect dangerous markup such as
script/iframe injection, DOM event attributes (onload, onerror), and javascript: protocol URIs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Dangerous tags that could lead to script execution or layout hijacks
DANGEROUS_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "link",
    "meta",
    "style",
    "form",
    "input",
    "button",
    "base",
    "applet",
}

# Permitted formatting tags
SAFE_FORMATTING_TAGS = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "span",
    "br",
    "p",
    "a",
    "code",
    "pre",
    "small",
    "sub",
    "sup",
}

EVENT_HANDLER_REGEX = re.compile(r"\bon[a-zA-Z]+\s*=", re.IGNORECASE)
JAVASCRIPT_URI_REGEX = re.compile(r"(?:href|src)\s*=\s*['\"]\s*javascript:", re.IGNORECASE)
HTML_TAG_REGEX = re.compile(r"<\s*(?P<closing>/)?\s*(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*)>", re.IGNORECASE)

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
    "coverage",
}


def audit_translation_string(
    text: str,
    key_path: str,
    file_path: str,
    safe_tags: Set[str],
) -> List[Dict[str, Any]]:
    """Inspect a single translation string for unsafe markup."""
    findings: List[Dict[str, Any]] = []

    # Check 1: Event handlers like onerror=, onload=, onclick=
    if EVENT_HANDLER_REGEX.search(text):
        findings.append({
            "file": file_path,
            "key": key_path,
            "type": "UNSAFE_EVENT_HANDLER",
            "severity": "ERROR",
            "snippet": text,
            "message": f"Translation key '{key_path}' contains inline event handler attribute.",
        })

    # Check 2: JavaScript URI protocol
    if JAVASCRIPT_URI_REGEX.search(text):
        findings.append({
            "file": file_path,
            "key": key_path,
            "type": "UNSAFE_JAVASCRIPT_URI",
            "severity": "ERROR",
            "snippet": text,
            "message": f"Translation key '{key_path}' contains dangerous 'javascript:' protocol URI.",
        })

    # Check 3: HTML tags (check opening tags only to avoid duplicate reports on closing tags)
    for match in HTML_TAG_REGEX.finditer(text):
        if match.group("closing"):
            continue
        tag_name = match.group("tag").lower()
        if tag_name in DANGEROUS_TAGS:
            findings.append({
                "file": file_path,
                "key": key_path,
                "type": "DANGEROUS_HTML_TAG",
                "severity": "ERROR",
                "snippet": match.group(0),
                "message": f"Translation key '{key_path}' contains prohibited HTML tag '<{tag_name}>'.",
            })
        elif tag_name not in safe_tags:
            findings.append({
                "file": file_path,
                "key": key_path,
                "type": "UNAPPROVED_HTML_TAG",
                "severity": "WARNING",
                "snippet": match.group(0),
                "message": f"Translation key '{key_path}' contains unapproved HTML tag '<{tag_name}>'.",
            })

    return findings


def walk_json_strings(
    data: Any, prefix: str = ""
) -> List[Tuple[str, str]]:
    """Recursively collect (key_path, string_value) tuples from nested JSON data."""
    results: List[Tuple[str, str]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            child_prefix = f"{prefix}.{k}" if prefix else k
            results.extend(walk_json_strings(v, child_prefix))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            child_prefix = f"{prefix}[{idx}]"
            results.extend(walk_json_strings(item, child_prefix))
    elif isinstance(data, str):
        results.append((prefix, data))
    return results


class I18nSafetyAuditor:
    """Audits i18n JSON files for HTML safety and XSS prevention."""

    def __init__(self, safe_tags: Optional[Set[str]] = None):
        self.safe_tags = (
            {t.lower() for t in safe_tags}
            if safe_tags is not None
            else SAFE_FORMATTING_TAGS
        )

    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries = walk_json_strings(data)
            for key_path, text in entries:
                findings.extend(
                    audit_translation_string(text, key_path, str(file_path), self.safe_tags)
                )
        except Exception as err:
            findings.append({
                "file": str(file_path),
                "key": "",
                "type": "JSON_PARSE_ERROR",
                "severity": "ERROR",
                "snippet": str(err),
                "message": f"Failed to parse JSON locale file: {err}",
            })
        return findings

    def scan_directory(self, root_path: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                if file.endswith(".json"):
                    # Check if file is in a translation or locale directory
                    parent_names = {p.lower() for p in Path(root).parts}
                    if any(loc in parent_names for loc in {"locales", "i18n", "messages", "lang", "translations"}):
                        findings.extend(self.scan_file(Path(root) / file))

        return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit i18n locale files for HTML tag safety and XSS vulnerabilities."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root path to scan (default: current directory).",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with non-zero code on unapproved tag warnings.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )

    args = parser.parse_args()
    auditor = I18nSafetyAuditor()
    findings = auditor.scan_directory(args.root)

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
        print("i18n HTML Safety & XSS Audit")
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}\n")

        for f in findings:
            prefix = "[ERROR]" if f.get("severity") == "ERROR" else "[WARNING]"
            print(f"{prefix} [{f['type']}] ({f['file']}:{f['key']}): {f['message']}")

    if errors:
        return 1
    if warnings and args.fail_on_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
