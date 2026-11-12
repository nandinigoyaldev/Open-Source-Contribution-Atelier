#!/usr/bin/env python3
"""Audit package dependencies for version conflicts, duplicates, and license compliance.

Scans package manifests (package.json and requirements.txt) across the workspace
to detect duplicate dependencies with incompatible versions, internal conflicts
between production and development dependencies, and restricted or prohibited software licenses.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_APPROVED_LICENSES = {
    "MIT",
    "APACHE-2.0",
    "BSD-2-CLAUSE",
    "BSD-3-CLAUSE",
    "ISC",
    "CC0-1.0",
    "0BSD",
    "UNLICENSE",
    "PYTHON-2.0",
}

DISALLOWED_LICENSES = {
    "GPL-2.0",
    "GPL-3.0",
    "AGPL-3.0",
    "AGPL-1.0",
    "SSPL",
    "COMMERCIAL",
    "PROPRIETARY",
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


def normalize_pkg_name(name: str) -> str:
    """Normalize package names by lowercasing and standardizing dashes/underscores."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def parse_package_json(path: Path) -> Dict[str, Any]:
    """Parse a package.json file and return structured dependency and license info."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    license_val = data.get("license", "")
    if isinstance(license_val, dict):
        license_str = license_val.get("type", "")
    elif isinstance(license_val, str):
        license_str = license_val
    else:
        license_str = ""

    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    peer_deps = data.get("peerDependencies", {})

    return {
        "file": str(path),
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "license": license_str.strip(),
        "dependencies": deps if isinstance(deps, dict) else {},
        "devDependencies": dev_deps if isinstance(dev_deps, dict) else {},
        "peerDependencies": peer_deps if isinstance(peer_deps, dict) else {},
    }


def parse_requirements_txt(path: Path) -> List[Tuple[str, str]]:
    """Parse requirements.txt into list of (package_name, version_specifier)."""
    results: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r") or line.startswith("-e"):
                continue

            # Strip inline comments
            line = line.split(" #")[0].strip()

            # Split package name and version specification
            match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", line)
            if match:
                pkg_name = match.group(1)
                spec = match.group(2).strip()
                results.append((pkg_name, spec))
    return results


class DependencyAuditor:
    """Audits repository package dependencies and license declarations."""

    def __init__(
        self,
        approved_licenses: Optional[Set[str]] = None,
        disallowed_licenses: Optional[Set[str]] = None,
    ):
        self.approved_licenses = (
            {lic.upper() for lic in approved_licenses}
            if approved_licenses is not None
            else DEFAULT_APPROVED_LICENSES
        )
        self.disallowed_licenses = (
            {lic.upper() for lic in disallowed_licenses}
            if disallowed_licenses is not None
            else DISALLOWED_LICENSES
        )

    def check_license(self, license_name: str, file_path: str) -> Optional[Dict[str, str]]:
        """Validate if a license declaration is acceptable."""
        cleaned = license_name.strip().upper()
        if not cleaned:
            return {
                "type": "LICENSE_MISSING",
                "severity": "WARNING",
                "file": file_path,
                "message": f"Package manifest '{file_path}' has no declared license.",
            }

        # Check for disallowed copyleft or commercial licenses
        for disallowed in self.disallowed_licenses:
            if disallowed in cleaned:
                return {
                    "type": "LICENSE_DISALLOWED",
                    "severity": "ERROR",
                    "file": file_path,
                    "message": f"Manifest '{file_path}' declares prohibited license '{license_name}'.",
                }

        # Check against approved permissive licenses
        if cleaned not in self.approved_licenses and not any(
            app in cleaned for app in self.approved_licenses
        ):
            return {
                "type": "LICENSE_UNAPPROVED",
                "severity": "WARNING",
                "file": file_path,
                "message": f"Manifest '{file_path}' declares unapproved license '{license_name}'.",
            }

        return None

    def check_single_package_json(self, pkg_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Check a single package.json for internal overlap between deps and devDeps."""
        findings: List[Dict[str, str]] = []
        file_path = pkg_data["file"]

        # Check license
        lic_finding = self.check_license(pkg_data.get("license", ""), file_path)
        if lic_finding:
            findings.append(lic_finding)

        deps = {normalize_pkg_name(k): v for k, v in pkg_data.get("dependencies", {}).items()}
        dev_deps = {normalize_pkg_name(k): v for k, v in pkg_data.get("devDependencies", {}).items()}

        overlap = set(deps.keys()) & set(dev_deps.keys())
        for pkg in sorted(overlap):
            v_dep = deps[pkg]
            v_dev = dev_deps[pkg]
            if v_dep != v_dev:
                findings.append({
                    "type": "INTERNAL_VERSION_CONFLICT",
                    "severity": "ERROR",
                    "file": file_path,
                    "message": f"Package '{pkg}' declared in both dependencies ('{v_dep}') and devDependencies ('{v_dev}') with differing versions.",
                })
            else:
                findings.append({
                    "type": "REDUNDANT_DEPENDENCY",
                    "severity": "WARNING",
                    "file": file_path,
                    "message": f"Package '{pkg}' redundantly declared in both dependencies and devDependencies.",
                })

        return findings

    def check_cross_package_json(
        self, manifests: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Check across multiple package.json manifests for divergent versions of the same library."""
        findings: List[Dict[str, str]] = []
        global_dep_map: Dict[str, Dict[str, List[str]]] = {}

        for manifest in manifests:
            file_path = manifest["file"]
            all_deps = {}
            all_deps.update(manifest.get("dependencies", {}))
            all_deps.update(manifest.get("devDependencies", {}))

            for name, version in all_deps.items():
                norm = normalize_pkg_name(name)
                if norm not in global_dep_map:
                    global_dep_map[norm] = {}
                if version not in global_dep_map[norm]:
                    global_dep_map[norm][version] = []
                global_dep_map[norm][version].append(file_path)

        for pkg, versions in global_dep_map.items():
            if len(versions) > 1:
                # Multiple distinct version specs across packages
                ver_summary = ", ".join(
                    f"{v} in [{', '.join(paths)}]" for v, paths in sorted(versions.items())
                )
                findings.append({
                    "type": "CROSS_PACKAGE_VERSION_DIVERGENCE",
                    "severity": "WARNING",
                    "package": pkg,
                    "message": f"Cross-package divergence for '{pkg}': multiple version specifications: {ver_summary}",
                })

        return findings

    def check_requirements_txt(
        self, files: List[Tuple[Path, List[Tuple[str, str]]]]
    ) -> List[Dict[str, str]]:
        """Audit Python requirements.txt files for duplicate entries and version clashes."""
        findings: List[Dict[str, str]] = []

        for path, entries in files:
            seen: Dict[str, str] = {}
            for pkg, spec in entries:
                norm = normalize_pkg_name(pkg)
                if norm in seen:
                    prev_spec = seen[norm]
                    if prev_spec != spec:
                        findings.append({
                            "type": "REQUIREMENTS_DUPLICATE_CONFLICT",
                            "severity": "ERROR",
                            "file": str(path),
                            "message": f"Package '{pkg}' listed multiple times with conflicting specs: '{prev_spec}' vs '{spec}'.",
                        })
                    else:
                        findings.append({
                            "type": "REQUIREMENTS_DUPLICATE_ENTRY",
                            "severity": "WARNING",
                            "file": str(path),
                            "message": f"Package '{pkg}' listed multiple times redundantly.",
                        })
                else:
                    seen[norm] = spec

        return findings

    def audit_directory(self, root_path: Path) -> List[Dict[str, str]]:
        """Scan directory and audit all package.json and requirements.txt files."""
        findings: List[Dict[str, str]] = []
        pkg_json_data: List[Dict[str, Any]] = []
        req_txt_data: List[Tuple[Path, List[Tuple[str, str]]]] = []

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                file_path = Path(root) / file
                if file == "package.json":
                    try:
                        data = parse_package_json(file_path)
                        pkg_json_data.append(data)
                        findings.extend(self.check_single_package_json(data))
                    except Exception as err:
                        findings.append({
                            "type": "PARSE_ERROR",
                            "severity": "ERROR",
                            "file": str(file_path),
                            "message": f"Failed to parse package.json: {err}",
                        })
                elif file.endswith("requirements.txt") or file == "requirements.txt":
                    try:
                        parsed_reqs = parse_requirements_txt(file_path)
                        req_txt_data.append((file_path, parsed_reqs))
                    except Exception as err:
                        findings.append({
                            "type": "PARSE_ERROR",
                            "severity": "ERROR",
                            "file": str(file_path),
                            "message": f"Failed to parse requirements file: {err}",
                        })

        findings.extend(self.check_cross_package_json(pkg_json_data))
        findings.extend(self.check_requirements_txt(req_txt_data))

        return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit package dependencies for duplicates, version divergence, and license compliance."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root path to scan (default: current working directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with failure if any warnings are detected.",
    )

    args = parser.parse_args()
    auditor = DependencyAuditor()
    findings = auditor.audit_directory(args.root)

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
        print(f"Dependency Audit Report for: {args.root.resolve()}")
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}\n")

        for f in findings:
            sev = f.get("severity", "INFO")
            ftype = f.get("type", "UNKNOWN")
            msg = f.get("message", "")
            fpath = f.get("file") or f.get("package") or ""
            prefix = "[ERROR]" if sev == "ERROR" else "[WARNING]"
            print(f"{prefix} [{ftype}] ({fpath}): {msg}")

    if errors:
        return 1
    if warnings and args.fail_on_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
