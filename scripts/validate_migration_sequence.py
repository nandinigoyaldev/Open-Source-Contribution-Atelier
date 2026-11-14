#!/usr/bin/env python3
"""Validate database migration sequence integrity and branch collisions.

Audits database migration folders (Prisma, Alembic, Knex, Flyway, SQL) to detect
duplicate sequence prefix collisions, out-of-order version numbering, and irregular
migration file naming.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

MIGRATION_EXTENSIONS = {".sql", ".ts", ".js", ".py"}

# Patterns for migration prefixes:
# 1. Numeric: e.g. 0001_initial_schema.sql, 01_users.sql, 003-posts.ts
NUMERIC_PREFIX_REGEX = re.compile(r"^(?P<prefix>\d{2,6})[_\-](?P<name>.*)$")

# 2. Timestamp: e.g. 20260101120000_create_audit_log.sql, 2026-01-01-120000_posts.sql
TIMESTAMP_PREFIX_REGEX = re.compile(
    r"^(?P<prefix>\d{4}[-_]?\d{2}[-_]?\d{2}[-_]?\d{4,6})[_\-](?P<name>.*)$"
)


def parse_migration_filename(filename: str) -> Optional[Tuple[str, str, str]]:
    """Parse a filename into (prefix_type, prefix_value, descriptive_name).

    Returns None if filename is not recognized as a migration format or is a meta file.
    """
    stem = Path(filename).stem

    # Ignore meta/template files like __init__.py, schema.prisma, README.md
    if stem.startswith("__") or stem.lower() in {"readme", "index", "schema"}:
        return None

    # Check timestamp first (more specific)
    match_ts = TIMESTAMP_PREFIX_REGEX.match(stem)
    if match_ts:
        cleaned_prefix = re.sub(r"[-_]", "", match_ts.group("prefix"))
        return ("timestamp", cleaned_prefix, match_ts.group("name"))

    match_num = NUMERIC_PREFIX_REGEX.match(stem)
    if match_num:
        return ("numeric", match_num.group("prefix"), match_num.group("name"))

    return None


class MigrationSequenceValidator:
    """Validates sequence order and uniqueness across migration files."""

    def __init__(self, strict_monotonic: bool = False):
        self.strict_monotonic = strict_monotonic

    def validate_directory(self, migration_dir: Path) -> List[Dict[str, Any]]:
        """Validate migrations in a specific folder."""
        findings: List[Dict[str, Any]] = []
        if not migration_dir.is_dir():
            return findings

        entries = sorted([
            p for p in migration_dir.iterdir()
            if p.is_file() and p.suffix.lower() in MIGRATION_EXTENSIONS
        ])

        seen_prefixes: Dict[str, List[Path]] = {}
        numeric_sequence: List[Tuple[int, Path]] = []
        timestamp_sequence: List[Tuple[str, Path]] = []

        for p in entries:
            parsed = parse_migration_filename(p.name)
            if not parsed:
                # File has migration extension but irregular prefix
                findings.append({
                    "file": str(p),
                    "type": "INVALID_MIGRATION_FILENAME",
                    "severity": "WARNING",
                    "message": f"File '{p.name}' does not follow numeric or timestamp migration naming conventions.",
                })
                continue

            ptype, prefix, name = parsed

            if prefix not in seen_prefixes:
                seen_prefixes[prefix] = []
            seen_prefixes[prefix].append(p)

            if ptype == "numeric":
                numeric_sequence.append((int(prefix), p))
            elif ptype == "timestamp":
                timestamp_sequence.append((prefix, p))

        # Check 1: Prefix collisions
        for prefix, files in seen_prefixes.items():
            if len(files) > 1:
                file_names = ", ".join(f.name for f in files)
                findings.append({
                    "prefix": prefix,
                    "directory": str(migration_dir),
                    "type": "MIGRATION_PREFIX_COLLISION",
                    "severity": "ERROR",
                    "message": f"Collision detected for migration prefix '{prefix}': [{file_names}].",
                })

        # Check 2: Monotonic integer sequences
        if numeric_sequence:
            # Sort by filename order as on disk
            raw_nums = [n for n, _ in numeric_sequence]
            sorted_nums = sorted(raw_nums)

            if raw_nums != sorted_nums:
                findings.append({
                    "directory": str(migration_dir),
                    "type": "OUT_OF_ORDER_MIGRATIONS",
                    "severity": "ERROR",
                    "message": "Numeric migrations are out of alphabetical/sequence order on disk.",
                })

            if self.strict_monotonic and sorted_nums:
                # Check for gaps (e.g. 1, 2, 4 missing 3)
                start = sorted_nums[0]
                expected = list(range(start, start + len(sorted_nums)))
                if sorted_nums != expected:
                    findings.append({
                        "directory": str(migration_dir),
                        "type": "SEQUENCE_GAP",
                        "severity": "WARNING",
                        "message": f"Gaps detected in numeric migration sequence: found {sorted_nums}, expected {expected}.",
                    })

        # Check 3: Timestamp ordering
        if timestamp_sequence:
            raw_ts = [ts for ts, _ in timestamp_sequence]
            sorted_ts = sorted(raw_ts)
            if raw_ts != sorted_ts:
                findings.append({
                    "directory": str(migration_dir),
                    "type": "OUT_OF_ORDER_MIGRATIONS",
                    "severity": "ERROR",
                    "message": "Timestamp migrations are out of chronological order on disk.",
                })

        return findings

    def scan_workspace(self, root_path: Path) -> List[Dict[str, Any]]:
        """Discover all migration directories and validate each."""
        findings: List[Dict[str, Any]] = []

        for root, dirs, _ in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            dir_name = Path(root).name.lower()
            # Recognize migration folders
            if "migration" in dir_name or dir_name == "migrations":
                findings.extend(self.validate_directory(Path(root)))

        return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate database migration sequence integrity and prefix collisions."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Specific migration directory to validate (default: auto-discover across workspace).",
    )
    parser.add_argument(
        "--strict-monotonic",
        action="store_true",
        help="Enforce strictly continuous sequential numbers without gaps.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with error on warnings.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )

    args = parser.parse_args()
    validator = MigrationSequenceValidator(strict_monotonic=args.strict_monotonic)

    if args.dir:
        findings = validator.validate_directory(args.dir)
    else:
        findings = validator.scan_workspace(Path("."))

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
        print("Database Migration Integrity Audit")
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}\n")

        for f in findings:
            prefix = "[ERROR]" if f.get("severity") == "ERROR" else "[WARNING]"
            loc = f.get("file") or f.get("directory") or f.get("prefix") or ""
            print(f"{prefix} [{f['type']}] ({loc}): {f['message']}")

    if errors:
        return 1
    if warnings and args.fail_on_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
