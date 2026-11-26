#!/usr/bin/env python3
"""Generate a reproducible dependency license summary for release reporting.

Covers both frontend (``package-lock.json``) and backend (``requirements*.txt``)
dependencies without modifying dependency resolution or mutating lockfiles.

Usage:
    python scripts/release_license_report.py
    python scripts/release_license_report.py --output release-license-report.json
    python scripts/release_license_report.py --fail-on-unknown --fail-on-disallowed
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.audit_dependency_licenses_and_duplicates import (  # noqa: E402
    DependencyAuditor,
    normalize_pkg_name,
    parse_requirements_txt,
)

DEFAULT_NPM_LOCKFILES = ("frontend/package-lock.json", "package-lock.json")
DEFAULT_REQUIREMENTS_FILES = (
    "backend/requirements-prod.txt",
    "backend/requirements.txt",
    "services/notifications_worker/requirements.txt",
)

UNKNOWN_LICENSE_TOKENS = {"", "UNKNOWN", "NONE", "N/A", "NA", "UNSPECIFIED"}

CLASSIFIER_LICENSE_MAP = {
    "MIT LICENSE": "MIT",
    "APACHE SOFTWARE LICENSE": "Apache-2.0",
    "BSD LICENSE": "BSD",
    "ISC LICENSE (ISCL)": "ISC",
    "MOZILLA PUBLIC LICENSE 2.0 (MPL 2.0)": "MPL-2.0",
    "PYTHON SOFTWARE FOUNDATION LICENSE": "PSF-2.0",
    "PUBLIC DOMAIN": "Public-Domain",
    "CC0 1.0 UNIVERSAL (CC0 1.0) PUBLIC DOMAIN DEDICATION": "CC0-1.0",
    "ZERO-CLAUSE BSD (0BSD)": "0BSD",
    "THE UNLICENSE (UNLICENSE)": "Unlicense",
    "GNU GENERAL PUBLIC LICENSE V2 (GPLV2)": "GPL-2.0",
    "GNU GENERAL PUBLIC LICENSE V3 (GPLV3)": "GPL-3.0",
    "GNU AFFERO GENERAL PUBLIC LICENSE V3 (AGPLV3)": "AGPL-3.0",
}

MetadataResolver = Callable[[str], Optional[Tuple[str, str]]]


def _extract_npm_package_name(pkg_key: str, meta: Dict[str, Any]) -> str:
    explicit = str(meta.get("name") or "").strip()
    if explicit:
        return explicit
    if "node_modules/" in pkg_key:
        return pkg_key.rsplit("node_modules/", 1)[-1]
    return pkg_key


def _normalize_license_value(raw_license: Any) -> str:
    if isinstance(raw_license, str):
        cleaned = " ".join(raw_license.strip().split())
    elif isinstance(raw_license, dict):
        cleaned = " ".join(
            str(raw_license.get("type") or raw_license.get("name") or "").split()
        )
    elif isinstance(raw_license, list):
        parts = [_normalize_license_value(item) for item in raw_license]
        cleaned = " OR ".join(p for p in parts if p and p != "UNKNOWN")
    else:
        cleaned = ""

    upper = cleaned.upper()
    if upper in UNKNOWN_LICENSE_TOKENS or upper.startswith("SEE LICENSE"):
        return "UNKNOWN"
    return cleaned


def _classifier_to_license(classifiers: Sequence[str]) -> str:
    found: List[str] = []
    for raw in classifiers:
        if not raw.startswith("License ::"):
            continue
        leaf = raw.rsplit("::", 1)[-1].strip()
        if leaf.upper() == "OSI APPROVED":
            continue
        mapped = CLASSIFIER_LICENSE_MAP.get(leaf.upper(), leaf)
        if mapped and mapped not in found:
            found.append(mapped)
    return " OR ".join(found) if found else "UNKNOWN"


def build_installed_python_metadata_index() -> Dict[str, Tuple[str, str]]:
    """Build deterministic {normalized_name: (version, license)} from Python env."""
    index: Dict[str, Tuple[str, str]] = {}
    for dist in importlib.metadata.distributions():
        raw_name = dist.metadata.get("Name") or ""
        if not raw_name:
            continue
        norm = normalize_pkg_name(raw_name)
        version = str(dist.version or "").strip()

        expr = dist.metadata.get("License-Expression") or ""
        lic = _normalize_license_value(expr)
        if lic == "UNKNOWN":
            raw_lic = dist.metadata.get("License") or ""
            # Ignore multi-line full LICENSE blobs in legacy package metadata.
            if "\n" not in raw_lic and len(raw_lic.strip()) <= 80:
                lic = _normalize_license_value(raw_lic)
        if lic == "UNKNOWN":
            classifiers = dist.metadata.get_all("Classifier") or []
            lic = _classifier_to_license(list(classifiers))

        if norm not in index:
            index[norm] = (version, lic)
    return index


def load_external_license_metadata(
    path: Optional[Path],
) -> Dict[str, Tuple[str, str]]:
    """Load optional external JSON license metadata (e.g. pip-licenses output)."""
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: Iterable[Dict[str, Any]]
    if isinstance(payload, dict):
        records = payload.get("packages") or payload.get("dependencies") or []
    elif isinstance(payload, list):
        records = payload
    else:
        return {}

    mapping: Dict[str, Tuple[str, str]] = {}
    for entry in records:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("Name") or entry.get("name") or "").strip()
        if not name:
            continue
        version = str(entry.get("Version") or entry.get("version") or "").strip()
        raw_lic = entry.get("License") or entry.get("license") or ""
        mapping[normalize_pkg_name(name)] = (
            version,
            _normalize_license_value(raw_lic),
        )
    return mapping


def classify_license(license_name: str, auditor: DependencyAuditor) -> str:
    """Classify normalized license string into review categories."""
    if not license_name or license_name == "UNKNOWN":
        return "unknown"

    cleaned = license_name.strip().upper()
    for disallowed in sorted(auditor.disallowed_licenses, key=len, reverse=True):
        # Boundary match prevents e.g. 'LGPL-3.0-only' matching 'GPL-3.0'.
        if re.search(rf"(?<![A-Z0-9-]){re.escape(disallowed)}(?![A-Z0-9])", cleaned):
            return "disallowed"

    if cleaned in auditor.approved_licenses or any(
        re.search(rf"(?<![A-Z0-9-]){re.escape(app)}(?![A-Z0-9])", cleaned)
        for app in auditor.approved_licenses
    ):
        return "approved"
    return "unapproved"


def collect_npm_dependencies(
    root_path: Path,
    lockfile_relpaths: Sequence[str] = DEFAULT_NPM_LOCKFILES,
) -> List[Dict[str, Any]]:
    """Extract resolved npm package license records from package-lock.json files."""
    records: List[Dict[str, Any]] = []
    for rel in lockfile_relpaths:
        lock_path = root_path / rel
        if not lock_path.is_file():
            continue
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        source = Path(rel).as_posix()
        packages = data.get("packages")
        if isinstance(packages, dict):
            for pkg_key, meta in packages.items():
                if not pkg_key or not isinstance(meta, dict):
                    continue
                if meta.get("link"):
                    continue
                name = _extract_npm_package_name(pkg_key, meta)
                version = str(meta.get("version") or "").strip()
                lic = _normalize_license_value(meta.get("license"))
                records.append(
                    {
                        "ecosystem": "npm",
                        "scope": "frontend",
                        "source": source,
                        "name": name,
                        "version": version,
                        "license": lic,
                        "dev": bool(meta.get("dev", False)),
                    }
                )
        else:
            # Lockfile v1 fallback
            for dep_name, meta in (data.get("dependencies") or {}).items():
                if not isinstance(meta, dict):
                    continue
                records.append(
                    {
                        "ecosystem": "npm",
                        "scope": "frontend",
                        "source": source,
                        "name": dep_name,
                        "version": str(meta.get("version") or "").strip(),
                        "license": _normalize_license_value(meta.get("license")),
                        "dev": bool(meta.get("dev", False)),
                    }
                )
    return records


def collect_python_dependencies(
    root_path: Path,
    requirements_relpaths: Sequence[str] = DEFAULT_REQUIREMENTS_FILES,
    resolver: Optional[MetadataResolver] = None,
) -> List[Dict[str, Any]]:
    """Extract declared Python dependency records paired with license metadata."""
    if resolver is None:
        installed = build_installed_python_metadata_index()
        resolver = lambda norm_name: installed.get(norm_name)

    records: List[Dict[str, Any]] = []
    for rel in requirements_relpaths:
        req_path = root_path / rel
        if not req_path.is_file():
            continue
        source = Path(rel).as_posix()
        seen_in_file: set[str] = set()
        for raw_name, raw_spec in parse_requirements_txt(req_path):
            norm = normalize_pkg_name(raw_name)
            if norm in seen_in_file:
                continue
            seen_in_file.add(norm)
            clean_spec = raw_spec.split(";", 1)[0].strip()
            resolved = resolver(norm)
            if resolved is not None:
                resolved_ver, resolved_lic = resolved
                version = resolved_ver or clean_spec
                lic = _normalize_license_value(resolved_lic)
            else:
                version = clean_spec
                lic = "UNKNOWN"
            records.append(
                {
                    "ecosystem": "pypi",
                    "scope": "backend",
                    "source": source,
                    "name": norm,
                    "version": version,
                    "license": lic,
                    "dev": False,
                }
            )
    return records


def generate_release_license_report(
    root_path: Path,
    *,
    npm_lockfiles: Sequence[str] = DEFAULT_NPM_LOCKFILES,
    requirements_files: Sequence[str] = DEFAULT_REQUIREMENTS_FILES,
    external_python_metadata: Optional[Path] = None,
    metadata_resolver: Optional[MetadataResolver] = None,
    auditor: Optional[DependencyAuditor] = None,
) -> Dict[str, Any]:
    """Build a deterministic, machine-readable release dependency license report."""
    auditor_inst = auditor or DependencyAuditor()

    if metadata_resolver is None:
        installed = build_installed_python_metadata_index()
        external = load_external_license_metadata(external_python_metadata)
        merged_meta = {**installed, **external}
        resolver: MetadataResolver = lambda norm_name: merged_meta.get(norm_name)
    else:
        resolver = metadata_resolver

    raw_packages: List[Dict[str, Any]] = []
    raw_packages.extend(collect_npm_dependencies(root_path, npm_lockfiles))
    raw_packages.extend(
        collect_python_dependencies(root_path, requirements_files, resolver=resolver)
    )

    packages: List[Dict[str, Any]] = []
    for pkg in raw_packages:
        status = classify_license(pkg["license"], auditor_inst)
        packages.append(
            {
                "ecosystem": pkg["ecosystem"],
                "scope": pkg["scope"],
                "source": pkg["source"],
                "name": pkg["name"],
                "version": pkg["version"],
                "license": pkg["license"],
                "status": status,
                "dev": pkg["dev"],
            }
        )

    packages.sort(
        key=lambda p: (
            p["ecosystem"],
            p["source"],
            p["name"].lower(),
            p["version"],
        )
    )

    unknown_packages = [p for p in packages if p["status"] == "unknown"]
    disallowed_packages = [p for p in packages if p["status"] == "disallowed"]
    unapproved_packages = [p for p in packages if p["status"] == "unapproved"]
    review_required = [p for p in packages if p["status"] != "approved"]

    license_counter = Counter(p["license"] for p in packages)
    by_ecosystem: Dict[str, Dict[str, int]] = {}
    for eco in ("npm", "pypi"):
        eco_pkgs = [p for p in packages if p["ecosystem"] == eco]
        by_ecosystem[eco] = {
            "total": len(eco_pkgs),
            "approved": sum(1 for p in eco_pkgs if p["status"] == "approved"),
            "unknown": sum(1 for p in eco_pkgs if p["status"] == "unknown"),
            "unapproved": sum(1 for p in eco_pkgs if p["status"] == "unapproved"),
            "disallowed": sum(1 for p in eco_pkgs if p["status"] == "disallowed"),
        }

    return {
        "schema_version": 1,
        "summary": {
            "total_packages": len(packages),
            "frontend_packages": sum(1 for p in packages if p["scope"] == "frontend"),
            "backend_packages": sum(1 for p in packages if p["scope"] == "backend"),
            "approved_count": sum(1 for p in packages if p["status"] == "approved"),
            "unknown_count": len(unknown_packages),
            "unapproved_count": len(unapproved_packages),
            "disallowed_count": len(disallowed_packages),
            "review_required_count": len(review_required),
            "passed": not unknown_packages and not disallowed_packages,
        },
        "by_ecosystem": by_ecosystem,
        "license_counts": dict(sorted(license_counter.items())),
        "unknown_packages": unknown_packages,
        "disallowed_packages": disallowed_packages,
        "review_required": review_required,
        "packages": packages,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic release license report for frontend and backend "
            "dependencies without changing dependency resolution."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root directory (default: current directory).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the machine-readable JSON report.",
    )
    parser.add_argument(
        "--python-licenses-json",
        type=Path,
        default=None,
        help="Optional JSON file with Python package license metadata.",
    )
    parser.add_argument(
        "--fail-on-unknown",
        action="store_true",
        help="Exit non-zero if any dependency has an UNKNOWN license.",
    )
    parser.add_argument(
        "--fail-on-disallowed",
        action="store_true",
        help="Exit non-zero if any dependency declares a disallowed license.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Equivalent to --fail-on-unknown --fail-on-disallowed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the JSON report to stdout.",
    )
    args = parser.parse_args(argv)

    report = generate_release_license_report(
        args.root,
        external_python_metadata=args.python_licenses_json,
    )
    serialized = json.dumps(report, indent=2) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")

    summary = report["summary"]
    if args.json:
        print(serialized, end="")
    else:
        print(
            f"Release License Summary: total={summary['total_packages']} "
            f"(frontend={summary['frontend_packages']}, "
            f"backend={summary['backend_packages']}), "
            f"approved={summary['approved_count']}, "
            f"unknown={summary['unknown_count']}, "
            f"unapproved={summary['unapproved_count']}, "
            f"disallowed={summary['disallowed_count']}"
        )
        for pkg in report["disallowed_packages"]:
            print(
                f"  [DISALLOWED] {pkg['ecosystem']} {pkg['name']}@{pkg['version']} "
                f"({pkg['license']}) in {pkg['source']}"
            )
        for pkg in report["unknown_packages"]:
            print(
                f"  [UNKNOWN] {pkg['ecosystem']} {pkg['name']}@{pkg['version']} "
                f"in {pkg['source']}"
            )

    fail_unknown = args.strict or args.fail_on_unknown
    fail_disallowed = args.strict or args.fail_on_disallowed
    if fail_disallowed and summary["disallowed_count"] > 0:
        return 1
    if fail_unknown and summary["unknown_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
