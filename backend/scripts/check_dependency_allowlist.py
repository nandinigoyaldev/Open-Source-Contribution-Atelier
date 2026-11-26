"""
Check dependency scan reports against a vulnerability allowlist.

Usage:
    python backend/scripts/check_dependency_allowlist.py \\
        --reports-dir reports/ \\
        --allowlist backend/scripts/vuln-allowlist.json \\
        --output vuln-report-consolidated.json

Exits with code 1 if any HIGH/CRITICAL vulnerability not in the allowlist is found.
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.release_license_report import (
    generate_release_license_report,
)  # noqa: E402  # isort: skip


def load_allowlist(path):
    with open(path) as f:
        data = json.load(f)
    allowed_ids = {}
    for entry in data.get("allowed_cves", []):
        cve_id = entry.get("id", "").upper()
        reason = entry.get("reason", "")
        expires = entry.get("expires")
        if expires and date.fromisoformat(expires) < date.today():
            continue
        allowed_ids[cve_id] = reason
    allowed_pkgs = {
        p.get("name"): p.get("reason", "") for p in data.get("allowed_packages", [])
    }
    return allowed_ids, allowed_pkgs


def parse_pip_audit_report(path):
    vulnerabilities = []
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return vulnerabilities

    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulnerabilities", []):
            vulnerabilities.append(
                {
                    "id": vuln.get("id", "UNKNOWN"),
                    "package": dep.get("name", "unknown"),
                    "installed_version": dep.get("version", ""),
                    "severity": vuln.get("severity", "UNKNOWN").upper(),
                    "fix_version": (
                        vuln.get("fix_versions", [None])[0]
                        if vuln.get("fix_versions")
                        else None
                    ),
                    "source": "pip-audit",
                }
            )
    return vulnerabilities


def parse_npm_audit_report(path):
    vulnerabilities = []
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return vulnerabilities

    for advisory_id, advisory in data.get("advisories", {}).items():
        severity = advisory.get("severity", "unknown").upper()
        vulnerabilities.append(
            {
                "id": advisory.get("github_advisory_id", f"GHSA-{advisory_id}"),
                "package": advisory.get("module_name", "unknown"),
                "installed_version": advisory.get("found_version", ""),
                "severity": severity,
                "fix_version": advisory.get("patched_versions", ""),
                "source": "npm-audit",
            }
        )
    return vulnerabilities


def parse_grype_report(path):
    vulnerabilities = []
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return vulnerabilities

    for match in data.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        severity = vuln.get("severity", "unknown").upper()
        vulnerabilities.append(
            {
                "id": vuln.get("id", "UNKNOWN"),
                "package": artifact.get("name", "unknown"),
                "installed_version": artifact.get("version", ""),
                "severity": severity,
                "fix_version": (
                    vuln.get("fix", {}).get("versions", [None])[0]
                    if vuln.get("fix")
                    else None
                ),
                "source": "grype",
            }
        )
    return vulnerabilities


def filter_allowlist(vulnerabilities, allowed_ids, allowed_pkgs):
    unallowed = []
    allowed = []
    for v in vulnerabilities:
        cve_id = v["id"].upper()
        pkg_name = v["package"]
        severity = v.get("severity", "UNKNOWN")

        if cve_id in allowed_ids:
            v["allowlist_reason"] = allowed_ids[cve_id]
            allowed.append(v)
        elif pkg_name in allowed_pkgs:
            v["allowlist_reason"] = allowed_pkgs[pkg_name]
            allowed.append(v)
        elif severity in ("HIGH", "CRITICAL"):
            unallowed.append(v)
        else:
            allowed.append(v)
    return unallowed, allowed


def generate_csv_report(unallowed, allowed, output_path):
    fieldnames = [
        "id",
        "package",
        "installed_version",
        "severity",
        "fix_version",
        "source",
        "status",
        "allowlist_reason",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in unallowed:
            v["status"] = "UNALLOWED"
            writer.writerow(v)
        for v in allowed:
            v["status"] = "ALLOWED"
            writer.writerow(v)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check vulnerability reports against allowlist"
    )
    parser.add_argument(
        "--reports-dir", required=True, help="Directory containing scan reports"
    )
    parser.add_argument("--allowlist", required=True, help="Path to allowlist JSON")
    parser.add_argument(
        "--output",
        default="vuln-report-consolidated.json",
        help="Output consolidated report path",
    )
    parser.add_argument("--csv", default=None, help="Optional CSV output path")
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="Workspace root for collecting frontend/backend dependency licenses",
    )
    parser.add_argument(
        "--python-licenses-json",
        type=Path,
        default=None,
        help="Optional JSON metadata file for Python package licenses",
    )
    parser.add_argument(
        "--fail-on-unknown-licenses",
        action="store_true",
        help="Fail when any dependency license is UNKNOWN",
    )
    parser.add_argument(
        "--fail-on-disallowed-licenses",
        action="store_true",
        help="Fail when any dependency declares a disallowed license",
    )
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports_dir)
    allowed_ids, allowed_pkgs = load_allowlist(args.allowlist)

    all_vulnerabilities = []

    for pip_report in sorted(reports_dir.glob("vuln-report-pip*.json")):
        all_vulnerabilities.extend(parse_pip_audit_report(pip_report))
    for npm_report in sorted(reports_dir.glob("vuln-report-npm*.json")):
        all_vulnerabilities.extend(parse_npm_audit_report(npm_report))
    for grype_report in sorted(reports_dir.glob("vuln-report-grype*.json")):
        all_vulnerabilities.extend(parse_grype_report(grype_report))

    unallowed, allowed = filter_allowlist(
        all_vulnerabilities, allowed_ids, allowed_pkgs
    )
    license_report = generate_release_license_report(
        args.root,
        external_python_metadata=args.python_licenses_json,
    )
    lic_summary = license_report["summary"]

    consolidated = {
        "summary": {
            "total_vulnerabilities": len(all_vulnerabilities),
            "unallowed_count": len(unallowed),
            "allowed_count": len(allowed),
            "passed": len(unallowed) == 0,
            "license_total_packages": lic_summary["total_packages"],
            "license_unknown_count": lic_summary["unknown_count"],
            "license_disallowed_count": lic_summary["disallowed_count"],
            "license_review_required_count": lic_summary["review_required_count"],
        },
        "unallowed_vulnerabilities": sorted(
            unallowed, key=lambda v: (v["severity"], v["id"])
        ),
        "allowed_vulnerabilities": sorted(
            allowed, key=lambda v: (v["severity"], v["id"])
        ),
        "dependency_licenses": license_report,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2)

    if args.csv:
        generate_csv_report(unallowed, allowed, args.csv)

    print(
        f"Total: {len(all_vulnerabilities)}, Unallowed: {len(unallowed)}, Allowed: {len(allowed)}"
    )
    print(
        f"Licenses: total={lic_summary['total_packages']} "
        f"(frontend={lic_summary['frontend_packages']}, backend={lic_summary['backend_packages']}), "
        f"unknown={lic_summary['unknown_count']}, disallowed={lic_summary['disallowed_count']}"
    )

    if unallowed:
        print(f"FAIL: {len(unallowed)} HIGH/CRITICAL vulnerabilities not in allowlist")
        for v in unallowed:
            print(f"  [{v['severity']}] {v['id']} in {v['package']} ({v['source']})")
        return 1

    if args.fail_on_disallowed_licenses and lic_summary["disallowed_count"] > 0:
        print(
            f"FAIL: {lic_summary['disallowed_count']} disallowed dependency license(s) found"
        )
        for pkg in license_report["disallowed_packages"]:
            print(
                f"  [DISALLOWED] {pkg['ecosystem']} {pkg['name']}@{pkg['version']} ({pkg['license']})"
            )
        return 1

    if args.fail_on_unknown_licenses and lic_summary["unknown_count"] > 0:
        print(f"FAIL: {lic_summary['unknown_count']} dependency license(s) are UNKNOWN")
        for pkg in license_report["unknown_packages"]:
            print(
                f"  [UNKNOWN] {pkg['ecosystem']} {pkg['name']}@{pkg['version']} in {pkg['source']}"
            )
        return 1

    print("PASS: No unallowed HIGH/CRITICAL vulnerabilities found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
