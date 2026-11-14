#!/usr/bin/env python3
"""
Curriculum frontmatter and metadata integrity validator.

Validates frontmatter in Markdown curriculum modules across attributes such as
title, slug, difficulty, estimated time, and prerequisites.

Usage:
    python scripts/validate_curriculum_frontmatter.py [--path PATH] [--strict]
"""

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}
SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_REGEX = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.DOTALL)


def parse_frontmatter(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Extract YAML-style key-value pairs from frontmatter block."""
    match = FRONTMATTER_REGEX.match(content)
    if not match:
        return None, "Missing or malformed frontmatter delimiter (---)"

    raw_block = match.group(1)
    metadata: Dict[str, Any] = {}

    for line_num, line in enumerate(raw_block.splitlines(), start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            return None, f"Invalid key-value syntax on frontmatter line {line_num}: {line}"

        key, val = stripped.split(":", 1)
        key = key.strip()
        val = val.strip()

        # Parse basic types
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            metadata[key] = val[1:-1]
        elif val.startswith("'") and val.endswith("'") and len(val) >= 2:
            metadata[key] = val[1:-1]
        elif val.startswith("[") and val.endswith("]"):
            items = [item.strip().strip("'\"") for item in val[1:-1].split(",") if item.strip()]
            metadata[key] = items
        elif val.lower() == "true":
            metadata[key] = True
        elif val.lower() == "false":
            metadata[key] = False
        elif val.isdigit():
            metadata[key] = int(val)
        else:
            metadata[key] = val

    return metadata, ""


def validate_metadata(metadata: Dict[str, Any], filepath: str, strict: bool = False) -> List[str]:
    """Validate extracted metadata against curriculum schema rules."""
    errors = []

    # Title check
    title = metadata.get("title")
    if not title:
        errors.append(f"{filepath}: 'title' is required and cannot be empty")
    elif not isinstance(title, str) or len(title.strip()) < 3:
        errors.append(f"{filepath}: 'title' must be a string of at least 3 characters")

    # Slug check
    slug = metadata.get("slug")
    if not slug:
        errors.append(f"{filepath}: 'slug' is required")
    elif not isinstance(slug, str) or not SLUG_REGEX.match(slug):
        errors.append(
            f"{filepath}: 'slug' must be lowercase alphanumeric with hyphens (received: {slug!r})"
        )

    # Difficulty check
    diff = metadata.get("difficulty")
    if not diff:
        errors.append(f"{filepath}: 'difficulty' is required")
    elif str(diff).lower() not in VALID_DIFFICULTIES:
        errors.append(
            f"{filepath}: 'difficulty' must be one of {sorted(VALID_DIFFICULTIES)} (received: {diff!r})"
        )

    # Estimated time check (optional unless strict)
    time_est = metadata.get("estimated_time_minutes")
    if time_est is not None:
        if not isinstance(time_est, int) or time_est <= 0:
            errors.append(
                f"{filepath}: 'estimated_time_minutes' must be a positive integer (received: {time_est!r})"
            )
    elif strict:
        errors.append(f"{filepath}: 'estimated_time_minutes' is required under --strict mode")

    # Prerequisites check
    prereqs = metadata.get("prerequisites")
    if prereqs is not None and not isinstance(prereqs, list):
        errors.append(f"{filepath}: 'prerequisites' must be a list of strings if provided")

    return errors


def validate_markdown_file(filepath: str, strict: bool = False) -> List[str]:
    """Validate a single markdown curriculum file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return [f"{filepath}: Could not read file: {e}"]

    metadata, err = parse_frontmatter(content)
    if err:
        return [f"{filepath}: {err}"]

    return validate_metadata(metadata or {}, filepath, strict=strict)


def validate_directory(target_dir: str, strict: bool = False) -> Tuple[int, List[str]]:
    """Scan directory recursively for .md files and validate them."""
    all_errors = []
    scanned_count = 0

    if not os.path.exists(target_dir):
        return 0, [f"Target path does not exist: {target_dir}"]

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".md"):
                scanned_count += 1
                fp = os.path.join(root, file)
                errors = validate_markdown_file(fp, strict=strict)
                all_errors.extend(errors)

    return scanned_count, all_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default="data/curriculum",
        help="Path to markdown file or directory to validate (default: data/curriculum)",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Enforce all optional fields strictly"
    )
    args = parser.parse_args()

    if os.path.isfile(args.path):
        errors = validate_markdown_file(args.path, strict=args.strict)
        count = 1
    else:
        count, errors = validate_directory(args.path, strict=args.strict)

    if errors:
        print(f"❌ Found {len(errors)} frontmatter issue(s) across {count} file(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"✅ Verified frontmatter integrity across {count} curriculum file(s) with 0 errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
