#!/usr/bin/env python3
"""
audit_security_headers_and_cors.py

Static analyzer that audits backend server configurations and middleware definitions for
defensive HTTP security response headers and safe Cross-Origin Resource Sharing (CORS) rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Set


class SecurityFinding(NamedTuple):
    severity: str  # "HIGH", "MEDIUM", "LOW"
    category: str
    message: str
    file_path: str
    line_number: int


REQUIRED_HEADERS = {
    "X-Content-Type-Options": re.compile(r"x-content-type-options|nosniff", re.IGNORECASE),
    "X-Frame-Options": re.compile(r"x-frame-options|deny|sameorigin|frameguard", re.IGNORECASE),
    "Strict-Transport-Security": re.compile(r"strict-transport-security|hsts|max-age", re.IGNORECASE),
    "Content-Security-Policy": re.compile(r"content-security-policy|contentSecurityPolicy|csp", re.IGNORECASE),
}

CORS_WILDCARD_PATTERN = re.compile(r"""(?:origin\s*:\s*['"]\*['"]|CORS_ALLOW_ALL_ORIGINS\s*=\s*True|allow_origins=\[.*?['"]\*['"].*?\])""", re.IGNORECASE)
CORS_CREDENTIALS_PATTERN = re.compile(r"""(?:credentials\s*:\s*true|CORS_ALLOW_CREDENTIALS\s*=\s*True|allow_credentials=True)""", re.IGNORECASE)
HELMET_PATTERN = re.compile(r"""(?:app\.use\s*\(\s*helmet\s*\(|import\s+helmet|require\s*\(\s*['"]helmet['"]\))""")
DJANGO_SECURITY_PATTERN = re.compile(r"""(?:django\.middleware\.security\.SecurityMiddleware|SECURE_SSL_REDIRECT|SECURE_HSTS_SECONDS)""")


def analyze_file_content(content: str, file_path: str) -> List[SecurityFinding]:
    findings: List[SecurityFinding] = []
    lines = content.splitlines()

    # Check for insecure CORS configurations: Wildcard Origin + Credentials
    has_wildcard = bool(CORS_WILDCARD_PATTERN.search(content))
    has_credentials = bool(CORS_CREDENTIALS_PATTERN.search(content))

    if has_wildcard and has_credentials:
        line_no = 1
        for idx, line in enumerate(lines, start=1):
            if CORS_WILDCARD_PATTERN.search(line) or CORS_CREDENTIALS_PATTERN.search(line):
                line_no = idx
                break
        findings.append(
            SecurityFinding(
                severity="HIGH",
                category="CORS",
                message="Insecure CORS policy: Wildcard origin ('*') combined with credentials enabled.",
                file_path=file_path,
                line_number=line_no,
            )
        )
    elif has_wildcard:
        line_no = 1
        for idx, line in enumerate(lines, start=1):
            if CORS_WILDCARD_PATTERN.search(line):
                line_no = idx
                break
        findings.append(
            SecurityFinding(
                severity="MEDIUM",
                category="CORS",
                message="Permissive CORS policy: Wildcard origin ('*') allows requests from any domain.",
                file_path=file_path,
                line_number=line_no,
            )
        )

    # Check for security header suites (Helmet, Django SecurityMiddleware)
    has_helmet = bool(HELMET_PATTERN.search(content))
    has_django_sec = bool(DJANGO_SECURITY_PATTERN.search(content))

    # If neither high-level security suite is present, check individual headers in server files
    is_server_file = any(name in file_path.lower() for name in ["server", "app", "main", "settings", "index"])
    if is_server_file and not (has_helmet or has_django_sec):
        missing_headers = []
        for header, pattern in REQUIRED_HEADERS.items():
            if not pattern.search(content):
                missing_headers.append(header)

        if missing_headers:
            findings.append(
                SecurityFinding(
                    severity="MEDIUM",
                    category="Headers",
                    message=f"Missing recommended security header protection: {', '.join(missing_headers)}. Consider using Helmet or SecurityMiddleware.",
                    file_path=file_path,
                    line_number=1,
                )
            )

    return findings


def scan_directory(root_dir: Path) -> List[SecurityFinding]:
    findings: List[SecurityFinding] = []
    target_extensions = {".js", ".ts", ".py", ".mjs"}
    ignore_dirs = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__"}

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in target_extensions:
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    rel_path = str(p.relative_to(root_dir))
                    findings.extend(analyze_file_content(content, rel_path))
                except Exception:
                    pass

    return findings


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit backend source code for security headers and CORS origin vulnerabilities."
    )
    parser.add_argument(
        "--path",
        "-p",
        type=Path,
        default=Path("."),
        help="Path to backend directory or file to audit (default: current directory).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with exit code 1 if any HIGH or MEDIUM severity security issues are discovered.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings formatted as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    target = args.path.resolve()

    if not target.exists():
        print(f"Error: Target path '{target}' does not exist.", file=sys.stderr)
        return 1

    findings: List[SecurityFinding] = []
    if target.is_file():
        content = target.read_text(encoding="utf-8", errors="replace")
        findings = analyze_file_content(content, target.name)
    else:
        findings = scan_directory(target)

    if args.json:
        payload = [
            {
                "severity": f.severity,
                "category": f.category,
                "message": f.message,
                "file_path": f.file_path,
                "line_number": f.line_number,
            }
            for f in findings
        ]
        print(json.dumps(payload, indent=2))
        if args.strict and any(f.severity in ("HIGH", "MEDIUM") for f in findings):
            return 1
        return 0

    print("=" * 60)
    print("Security Headers & CORS Policy Audit Report")
    print("=" * 60)

    if not findings:
        print("[+] No security header or CORS policy violations detected.")
        return 0

    high_count = sum(1 for f in findings if f.severity == "HIGH")
    med_count = sum(1 for f in findings if f.severity == "MEDIUM")
    low_count = sum(1 for f in findings if f.severity == "LOW")

    for f in findings:
        tag = f"[{f.severity}]"
        print(f"{tag:8} {f.file_path}:{f.line_number} -> {f.category}: {f.message}")

    print("\nSummary:")
    print(f"  HIGH Severity   : {high_count}")
    print(f"  MEDIUM Severity : {med_count}")
    print(f"  LOW Severity    : {low_count}")

    if high_count > 0 or (args.strict and med_count > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
