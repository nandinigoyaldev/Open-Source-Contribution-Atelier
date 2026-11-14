#!/usr/bin/env python3
"""
validate_whitespace_and_conflict_markers.py

Scans source code files for unresolved git merge conflict markers (<<<<<<<, =======, >>>>>>>)
and unhygienic trailing whitespace. Supports dry-run inspection, strict CI gating, and automated
whitespace remediation.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Set, Tuple

CONFLICT_PATTERNS = [
    re.compile(r"^<{7}(?: .+)?$"),
    re.compile(r"^={7}$"),
    re.compile(r"^>{7}(?: .+)?$"),
]

DEFAULT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".sh",
    ".toml",
}

DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".next",
}


class FileViolation(NamedTuple):
    file_path: Path
    conflict_markers: List[Tuple[int, str]]
    trailing_whitespace: List[int]


def is_binary_file(filepath: Path) -> bool:
    try:
        with open(filepath, "tr", encoding="utf-8") as check_file:
            check_file.read(1024)
            return False
    except (UnicodeDecodeError, PermissionError):
        return True


def inspect_file(file_path: Path) -> FileViolation:
    conflicts: List[Tuple[int, str]] = []
    trailing_spaces: List[int] = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return FileViolation(file_path=file_path, conflict_markers=[], trailing_whitespace=[])

    lines = content.splitlines(keepends=False)
    for idx, line in enumerate(lines, start=1):
        for pattern in CONFLICT_PATTERNS:
            if pattern.match(line):
                conflicts.append((idx, line))
                break
        if line.endswith(" ") or line.endswith("\t"):
            trailing_spaces.append(idx)

    return FileViolation(
        file_path=file_path,
        conflict_markers=conflicts,
        trailing_whitespace=trailing_spaces,
    )


def fix_trailing_whitespace(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        fixed_lines = [line.rstrip(" \t\r\n") + "\n" if line.endswith(("\r", "\n")) else line.rstrip(" \t") for line in lines]
        fixed_content = "".join(fixed_lines)
        if fixed_content != content:
            file_path.write_text(fixed_content, encoding="utf-8")
            return True
    except Exception:
        pass
    return False


def collect_target_files(
    root_dir: Path,
    extensions: Set[str] | None = None,
    excludes: Set[str] | None = None,
) -> List[Path]:
    exts = extensions or DEFAULT_EXTENSIONS
    excluded_names = excludes or DEFAULT_EXCLUDES
    collected: List[Path] = []

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in excluded_names and not d.startswith(".git")]
        for file_name in files:
            path = Path(root) / file_name
            if path.suffix.lower() in exts:
                if not is_binary_file(path):
                    collected.append(path)

    return sorted(collected)


def run_validation(
    target_path: Path,
    fix: bool = False,
    extensions: Set[str] | None = None,
    excludes: Set[str] | None = None,
) -> Tuple[List[FileViolation], int]:
    if target_path.is_file():
        files = [target_path]
    else:
        files = collect_target_files(target_path, extensions, excludes)

    violations: List[FileViolation] = []
    fixed_count = 0

    for file_path in files:
        violation = inspect_file(file_path)
        if violation.conflict_markers or violation.trailing_whitespace:
            violations.append(violation)
            if fix and violation.trailing_whitespace:
                if fix_trailing_whitespace(file_path):
                    fixed_count += 1

    return violations, fixed_count


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit source files for unresolved conflict markers and trailing whitespace."
    )
    parser.add_argument(
        "--path",
        "-p",
        type=Path,
        default=Path("."),
        help="Root directory or file path to inspect (default: current directory).",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically strip trailing whitespace from affected files.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with exit code 1 if any conflict markers or trailing whitespace are discovered.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    target = args.path.resolve()

    if not target.exists():
        print(f"Error: Target path '{target}' does not exist.", file=sys.stderr)
        return 1

    print(f"[*] Scanning '{target}' for conflict markers and trailing whitespace...")
    violations, fixed_count = run_validation(target, fix=args.fix)

    total_conflicts = sum(len(v.conflict_markers) for v in violations)
    total_trailing = sum(len(v.trailing_whitespace) for v in violations)

    if not violations:
        print("[+] All inspected files are clean! No conflict markers or trailing whitespace found.")
        return 0

    for v in violations:
        rel_path = v.file_path
        if v.conflict_markers:
            print(f"\n[!] MERGE CONFLICT in {rel_path}:")
            for line_no, raw in v.conflict_markers:
                print(f"    Line {line_no}: {raw}")
        if v.trailing_whitespace:
            lines_str = ", ".join(str(l) for l in v.trailing_whitespace[:5])
            more_str = f" (+{len(v.trailing_whitespace) - 5} more)" if len(v.trailing_whitespace) > 5 else ""
            print(f"[-] Trailing whitespace in {rel_path} on lines: {lines_str}{more_str}")

    print("\n" + "=" * 60)
    print(f"Summary: {len(violations)} file(s) with issues.")
    print(f"Conflict markers detected: {total_conflicts}")
    print(f"Trailing whitespace lines: {total_trailing}")
    if args.fix:
        print(f"Files remediated: {fixed_count}")

    if total_conflicts > 0 or (args.strict and total_trailing > 0 and not args.fix):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
