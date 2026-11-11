#!/usr/bin/env python3
"""
Markdown internal link and asset reference integrity checker.

Scans Markdown documents for relative links and asset references, verifying that
all referenced target files and images physically exist on disk.

Usage:
    python scripts/check_markdown_asset_integrity.py [--path PATH] [--quiet]
"""

import argparse
import os
import re
import sys
from typing import List, NamedTuple, Tuple
from urllib.parse import unquote, urlparse

LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
IGNORED_SCHEMES = {"http", "https", "mailto", "tel", "ftp", "javascript"}


class LinkRef(NamedTuple):
    source_file: str
    line_number: int
    raw_target: str
    resolved_path: str


def is_external_or_anchor(target: str) -> bool:
    """Return True if the target URL is external, mailto, or a local anchor."""
    clean = target.strip()
    if not clean or clean.startswith("#"):
        return True
    try:
        parsed = urlparse(clean)
        if parsed.scheme.lower() in IGNORED_SCHEMES:
            return True
    except Exception:
        pass
    return False


def extract_relative_links(file_path: str, content: str) -> List[LinkRef]:
    """Extract non-external links and assets from markdown text with line numbers."""
    links = []
    base_dir = os.path.dirname(os.path.abspath(file_path))

    for line_idx, line in enumerate(content.splitlines(), start=1):
        for match in LINK_PATTERN.finditer(line):
            raw_target = match.group(2).strip()
            # Split target in case it contains title or fragment: e.g. "path/to/file.md#anchor"
            path_part = raw_target.split()[0].split("#")[0].strip("<>")
            if is_external_or_anchor(path_part):
                continue

            decoded_path = unquote(path_part)
            # Handle repo-root relative path vs relative to file
            if decoded_path.startswith("/"):
                # Interpret relative to current working directory / repo root
                resolved = os.path.abspath(decoded_path.lstrip("/"))
            else:
                resolved = os.path.abspath(os.path.join(base_dir, decoded_path))

            links.append(
                LinkRef(
                    source_file=file_path,
                    line_number=line_idx,
                    raw_target=raw_target,
                    resolved_path=resolved,
                )
            )

    return links


def check_file(file_path: str) -> List[str]:
    """Scan a single markdown file for broken relative references."""
    errors = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return [f"{file_path}: Failed to read: {e}"]

    links = extract_relative_links(file_path, content)
    for ref in links:
        if not os.path.exists(ref.resolved_path):
            errors.append(
                f"{ref.source_file}:{ref.line_number}: Broken reference -> '{ref.raw_target}' "
                f"(not found at '{ref.resolved_path}')"
            )

    return errors


def scan_directory(target_path: str) -> Tuple[int, int, List[str]]:
    """Scan directory recursively for markdown files and verify links."""
    all_errors = []
    scanned_files = 0
    total_links_checked = 0

    if os.path.isfile(target_path):
        errs = check_file(target_path)
        return 1, len(errs), errs

    for root, _, files in os.walk(target_path):
        for f in files:
            if f.endswith(".md"):
                fp = os.path.join(root, f)
                scanned_files += 1
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        links = extract_relative_links(fp, fh.read())
                        total_links_checked += len(links)
                        for ref in links:
                            if not os.path.exists(ref.resolved_path):
                                all_errors.append(
                                    f"{ref.source_file}:{ref.line_number}: Broken reference -> "
                                    f"'{ref.raw_target}'"
                                )
                except Exception as e:
                    all_errors.append(f"{fp}: Read error: {e}")

    return scanned_files, total_links_checked, all_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default="docs",
        help="Path or directory to scan for markdown links (default: docs)",
    )
    parser.add_argument("--quiet", action="store_true", help="Print summary only")
    args = parser.parse_args()

    files, links, errors = scan_directory(args.path)

    if errors:
        print(f"❌ Detected {len(errors)} broken link(s) across {files} file(s):")
        if not args.quiet:
            for err in errors:
                print(f"  - {err}")
        return 1

    print(f"✅ Verified {links} internal references across {files} markdown file(s) with 0 errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
