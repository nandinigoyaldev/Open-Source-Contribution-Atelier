#!/usr/bin/env python3
"""Validate CSS theme color tokens and detect hardcoded hexadecimal values.

Scans frontend stylesheets (.css, .scss, .sass, .less) and component templates (.tsx, .jsx, .vue)
for hardcoded raw hex colors that bypass design tokens and CSS custom property variables.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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

STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".tsx", ".jsx", ".vue", ".html"}

# Matches hex color codes (#RGB, #RGBA, #RRGGBB, #RRGGBBAA)
# Word boundary or delimiter follows
HEX_COLOR_REGEX = re.compile(
    r"#(?P<hex>[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-fA-F])"
)

# Detects CSS variable definitions like `--primary-color: #0070f3;`
CSS_VAR_DEF_REGEX = re.compile(r"^\s*--[a-zA-Z0-9_\-]+\s*:\s*#[0-9a-fA-F]+")

# Ignore comments
IGNORE_PRAGMA_REGEX = re.compile(r"(allow-hex|no-color-lint)", re.IGNORECASE)


def is_valid_hex_color(hex_str: str) -> bool:
    """Ensure the hex string length is 3, 4, 6, or 8 chars and hexadecimal."""
    return len(hex_str) in {3, 4, 6, 8} and all(c in "0123456789abcdefABCDEF" for c in hex_str)


class CssColorTokenValidator:
    """Validates adherence to theme color tokens by flagging raw hex codes."""

    def __init__(
        self,
        allow_css_var_definitions: bool = True,
        allowed_hex_codes: Optional[Set[str]] = None,
    ):
        self.allow_css_var_defs = allow_css_var_definitions
        self.allowed_hex = {h.lower() for h in (allowed_hex_codes or set())}

    def scan_line(
        self, line: str, line_no: int, file_path: str
    ) -> List[Dict[str, Any]]:
        """Scan a single line for hardcoded hex colors."""
        findings: List[Dict[str, Any]] = []

        # Skip lines marked with ignore pragma
        if IGNORE_PRAGMA_REGEX.search(line):
            return findings

        # Skip token definitions inside CSS variable definitions if configured
        if self.allow_css_var_defs and CSS_VAR_DEF_REGEX.search(line):
            return findings

        matches = HEX_COLOR_REGEX.finditer(line)
        for match in matches:
            hex_val = match.group("hex")
            full_hex = f"#{hex_val}"

            if full_hex.lower() in self.allowed_hex:
                continue

            findings.append({
                "file": file_path,
                "line": line_no,
                "hex": full_hex,
                "snippet": line.strip(),
                "type": "HARDCODED_HEX_COLOR",
                "severity": "WARNING",
                "message": f"Hardcoded color '{full_hex}' found. Use CSS design tokens or theme variables instead.",
            })

        return findings

    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    findings.extend(self.scan_line(line, line_no, str(file_path)))
        except Exception:
            pass
        return findings

    def scan_directory(self, root_path: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in STYLE_EXTENSIONS:
                    file_path = Path(root) / file
                    findings.extend(self.scan_file(file_path))

        return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit stylesheets and UI components for hardcoded hex colors."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root path to scan (default: current directory).",
    )
    parser.add_argument(
        "--disallow-vars",
        action="store_true",
        help="Flag hex colors even in CSS custom variable definitions.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with non-zero code on any detected hardcoded hex colors.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )

    args = parser.parse_args()

    validator = CssColorTokenValidator(
        allow_css_var_definitions=not args.disallow_vars
    )
    findings = validator.scan_directory(args.root)

    if args.json:
        print(json.dumps({
            "total_findings": len(findings),
            "findings": findings,
        }, indent=2))
    else:
        print("CSS Theme Color Token Audit")
        print(f"Total hardcoded hex colors detected: {len(findings)}\n")

        for f in findings:
            print(f"[WARNING] [{f['type']}] {f['file']}:{f['line']} -> {f['hex']} in '{f['snippet']}'")

    if findings and args.fail_on_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
