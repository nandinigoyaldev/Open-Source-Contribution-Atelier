#!/usr/bin/env python3
"""Audit static media assets for file size budgets, uncompressed formats, and duplicates.

Traverses repository directories for images, vector graphics, audio, video, and webfonts,
enforcing maximum per-asset file size budgets, detecting duplicate media via SHA-256 hashes,
and recommending modern compressed web formats (WebP/AVIF).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Default size thresholds in bytes
DEFAULT_LIMITS = {
    "image": 500 * 1024,      # 500 KB for bitmap images (.png, .jpg, etc.)
    "svg": 150 * 1024,        # 150 KB for vector SVGs
    "video": 2 * 1024 * 1024, # 2 MB for video/audio clips
    "font": 300 * 1024,       # 300 KB for web fonts
}

ASSET_CATEGORIES: Dict[str, str] = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".avif": "image",
    ".svg": "svg",
    ".mp4": "video",
    ".webm": "video",
    ".mp3": "video",
    ".wav": "video",
    ".ogg": "video",
    ".woff2": "font",
    ".woff": "font",
    ".ttf": "font",
    ".otf": "font",
    ".eot": "font",
}

DISCOURAGED_FORMATS: Set[str] = {".bmp", ".tiff", ".tif"}

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


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def format_bytes(size: int) -> str:
    """Format bytes into readable string (B, KB, MB)."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    else:
        return f"{size / (1024 * 1024):.2f} MB"


class StaticAssetBudgetAuditor:
    """Audits static media assets against size budgets and optimization guidelines."""

    def __init__(
        self,
        limits: Optional[Dict[str, int]] = None,
        max_total_bytes: Optional[int] = None,
    ):
        self.limits = limits or DEFAULT_LIMITS
        self.max_total_bytes = max_total_bytes

    def audit_directory(self, root_path: Path) -> Dict[str, Any]:
        """Scan directory and audit all static media assets."""
        findings: List[Dict[str, Any]] = []
        assets_by_category: Dict[str, List[Dict[str, Any]]] = {
            "image": [],
            "svg": [],
            "video": [],
            "font": [],
            "discouraged": [],
        }
        seen_hashes: Dict[str, List[Path]] = {}
        total_payload_bytes = 0

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()

                if ext in DISCOURAGED_FORMATS:
                    size = file_path.stat().st_size
                    total_payload_bytes += size
                    assets_by_category["discouraged"].append({
                        "file": str(file_path),
                        "size": size,
                        "ext": ext,
                    })
                    findings.append({
                        "file": str(file_path),
                        "type": "DISCOURAGED_IMAGE_FORMAT",
                        "severity": "WARNING",
                        "size_bytes": size,
                        "message": f"Asset '{file_path.name}' uses uncompressed format '{ext}'. Consider converting to WebP or AVIF.",
                    })
                    continue

                category = ASSET_CATEGORIES.get(ext)
                if not category:
                    continue

                size = file_path.stat().st_size
                total_payload_bytes += size

                asset_info = {
                    "file": str(file_path),
                    "size": size,
                    "category": category,
                    "ext": ext,
                }
                assets_by_category[category].append(asset_info)

                # Check 1: Size threshold for category
                limit = self.limits.get(category)
                if limit and size > limit:
                    findings.append({
                        "file": str(file_path),
                        "type": "ASSET_SIZE_BUDGET_EXCEEDED",
                        "severity": "WARNING",
                        "size_bytes": size,
                        "limit_bytes": limit,
                        "message": f"Asset '{file_path.name}' ({format_bytes(size)}) exceeds maximum {category} budget of {format_bytes(limit)}.",
                    })

                # Check 2: Duplicate assets via SHA-256
                try:
                    file_hash = compute_sha256(file_path)
                    if file_hash not in seen_hashes:
                        seen_hashes[file_hash] = []
                    seen_hashes[file_hash].append(file_path)
                except Exception:
                    pass

        # Identify duplicates
        for sha, paths in seen_hashes.items():
            if len(paths) > 1:
                names = [str(p) for p in paths]
                findings.append({
                    "type": "DUPLICATE_STATIC_ASSET",
                    "severity": "WARNING",
                    "sha256": sha,
                    "files": names,
                    "message": f"Duplicate static assets detected sharing identical content: {names}",
                })

        # Check total budget
        if self.max_total_bytes and total_payload_bytes > self.max_total_bytes:
            findings.append({
                "type": "TOTAL_PAYLOAD_BUDGET_EXCEEDED",
                "severity": "ERROR",
                "total_bytes": total_payload_bytes,
                "limit_bytes": self.max_total_bytes,
                "message": f"Total static asset payload ({format_bytes(total_payload_bytes)}) exceeds total repository budget of {format_bytes(self.max_total_bytes)}.",
            })

        return {
            "total_assets_scanned": sum(len(v) for v in assets_by_category.values()),
            "total_payload_bytes": total_payload_bytes,
            "total_payload_formatted": format_bytes(total_payload_bytes),
            "findings": findings,
            "counts_by_category": {k: len(v) for k, v in assets_by_category.items()},
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit static media assets against size budgets and optimization guidelines."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root path to scan (default: current directory).",
    )
    parser.add_argument(
        "--max-img-kb",
        type=int,
        default=500,
        help="Maximum size budget for bitmap images in KB (default: 500).",
    )
    parser.add_argument(
        "--max-svg-kb",
        type=int,
        default=150,
        help="Maximum size budget for SVGs in KB (default: 150).",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with non-zero code on budget warnings.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )

    args = parser.parse_args()

    limits = {
        "image": args.max_img_kb * 1024,
        "svg": args.max_svg_kb * 1024,
        "video": DEFAULT_LIMITS["video"],
        "font": DEFAULT_LIMITS["font"],
    }

    auditor = StaticAssetBudgetAuditor(limits=limits)
    report = auditor.audit_directory(args.root)
    findings = report["findings"]

    errors = [f for f in findings if f.get("severity") == "ERROR"]
    warnings = [f for f in findings if f.get("severity") == "WARNING"]

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Static Asset Budget Audit")
        print(f"Total Assets: {report['total_assets_scanned']}, Total Payload: {report['total_payload_formatted']}")
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}\n")

        for f in findings:
            prefix = "[ERROR]" if f.get("severity") == "ERROR" else "[WARNING]"
            fpath = f.get("file") or (", ".join(f.get("files", []))) or ""
            print(f"{prefix} [{f['type']}] ({fpath}): {f['message']}")

    if errors:
        return 1
    if warnings and args.fail_on_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
