#!/usr/bin/env python3
"""Validate OpenAPI schema coverage and route parity against codebase implementations.

Compares documented OpenAPI/Swagger specifications with actual backend route definitions
(Express, Flask, FastAPI) to detect undocumented routes, orphaned specifications,
and path parameter mismatches.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

EXPRESS_ROUTE_REGEX = re.compile(
    r"\b(?:app|router|server)\.(?P<method>get|post|put|delete|patch)\s*\(\s*['\"](?P<path>/[^'\"]*)['\"]",
    re.IGNORECASE,
)

PYTHON_ROUTE_REGEX = re.compile(
    r"@(?:app|router|blueprint|bp)\.(?P<method>get|post|put|delete|patch)\s*\(\s*['\"](?P<path>/[^'\"]*)['\"]",
    re.IGNORECASE,
)

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


def normalize_route_path(path: str) -> str:
    """Normalize route path by standardizing parameters to {param} format and stripping trailing slashes."""
    # Convert Express style :param to {param}
    normalized = re.sub(r":([a-zA-Z0-9_]+)", r"{\1}", path.strip())
    # Strip trailing slash if longer than 1 character
    if len(normalized) > 1 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def extract_path_template(path: str) -> Tuple[str, List[str]]:
    """Extract generic template with wildcard parameter names and list of actual param names."""
    norm = normalize_route_path(path)
    params = re.findall(r"\{([^}]+)\}", norm)
    # Generic template replacing all param names with {}
    template = re.sub(r"\{[^}]+\}", "{}", norm)
    return template, params


def parse_openapi_spec(spec_path: Path) -> Dict[str, Dict[str, Any]]:
    """Parse OpenAPI spec (JSON or YAML) and return map of (method, path) -> info."""
    endpoints: Dict[str, Dict[str, Any]] = {}
    content = spec_path.read_text(encoding="utf-8")

    data: Dict[str, Any] = {}
    if spec_path.suffix.lower() == ".json":
        data = json.loads(content)
    else:
        # YAML support
        try:
            import yaml
            data = yaml.safe_load(content) or {}
        except ImportError:
            # Basic fallback for JSON-formatted YAML or raise
            try:
                data = json.loads(content)
            except Exception:
                raise RuntimeError(
                    f"PyYAML is not installed to parse YAML spec '{spec_path}'. Convert to JSON or install pyyaml."
                )

    paths = data.get("paths", {})
    if not isinstance(paths, dict):
        return endpoints

    valid_methods = {"get", "post", "put", "delete", "patch"}

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        norm_path = normalize_route_path(path_str)
        template, params = extract_path_template(norm_path)

        for method, operation in path_item.items():
            method_lower = method.lower()
            if method_lower in valid_methods and isinstance(operation, dict):
                key = f"{method_lower.upper()} {norm_path}"
                endpoints[key] = {
                    "method": method_lower.upper(),
                    "path": norm_path,
                    "template": template,
                    "params": params,
                    "summary": operation.get("summary", ""),
                    "operationId": operation.get("operationId", ""),
                }

    return endpoints


def scan_codebase_routes(root_path: Path) -> Dict[str, Dict[str, Any]]:
    """Scan code files for route definitions and return map of (method, path) -> info."""
    code_routes: Dict[str, Dict[str, Any]] = {}
    valid_extensions = {".js", ".ts", ".jsx", ".tsx", ".py"}

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            ext = Path(file).suffix.lower()
            if ext in valid_extensions:
                file_path = Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_no, line in enumerate(f, start=1):
                            # Express matches
                            for match in EXPRESS_ROUTE_REGEX.finditer(line):
                                method = match.group("method").upper()
                                raw_path = match.group("path")
                                norm_path = normalize_route_path(raw_path)
                                template, params = extract_path_template(norm_path)
                                key = f"{method} {norm_path}"
                                code_routes[key] = {
                                    "method": method,
                                    "path": norm_path,
                                    "template": template,
                                    "params": params,
                                    "file": str(file_path),
                                    "line": line_no,
                                }

                            # Python matches
                            for match in PYTHON_ROUTE_REGEX.finditer(line):
                                method = match.group("method").upper()
                                raw_path = match.group("path")
                                norm_path = normalize_route_path(raw_path)
                                template, params = extract_path_template(norm_path)
                                key = f"{method} {norm_path}"
                                code_routes[key] = {
                                    "method": method,
                                    "path": norm_path,
                                    "template": template,
                                    "params": params,
                                    "file": str(file_path),
                                    "line": line_no,
                                }
                except Exception:
                    pass

    return code_routes


class OpenApiCoverageValidator:
    """Validates parity and coverage between OpenAPI spec and code implementations."""

    def compare(
        self,
        spec_endpoints: Dict[str, Dict[str, Any]],
        code_routes: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Perform comparison between spec endpoints and code routes."""
        documented_keys = set(spec_endpoints.keys())
        implemented_keys = set(code_routes.keys())

        # Exact matches
        matched_keys = documented_keys & implemented_keys

        # Check template-level matches for endpoints with differing parameter names
        unmatched_code = implemented_keys - matched_keys
        unmatched_spec = documented_keys - matched_keys

        spec_by_template: Dict[Tuple[str, str], str] = {
            (v["method"], v["template"]): k for k, v in spec_endpoints.items() if k in unmatched_spec
        }

        template_matches: List[Dict[str, Any]] = []
        undocumented_routes: List[Dict[str, Any]] = []

        for code_key in sorted(unmatched_code):
            code_info = code_routes[code_key]
            template_key = (code_info["method"], code_info["template"])
            if template_key in spec_by_template:
                spec_key = spec_by_template[template_key]
                spec_info = spec_endpoints[spec_key]
                template_matches.append({
                    "code_endpoint": code_key,
                    "spec_endpoint": spec_key,
                    "code_params": code_info["params"],
                    "spec_params": spec_info["params"],
                })
                unmatched_spec.remove(spec_key)
                del spec_by_template[template_key]
            else:
                undocumented_routes.append(code_info)

        orphaned_specs: List[Dict[str, Any]] = [
            spec_endpoints[k] for k in sorted(unmatched_spec)
        ]

        total_implemented = len(implemented_keys)
        total_covered = len(matched_keys) + len(template_matches)
        coverage_pct = (
            (total_covered / total_implemented * 100.0) if total_implemented > 0 else 100.0
        )

        return {
            "total_implemented_routes": total_implemented,
            "total_spec_endpoints": len(spec_endpoints),
            "matched_count": len(matched_keys),
            "template_matched_count": len(template_matches),
            "coverage_percentage": round(coverage_pct, 2),
            "undocumented_routes": undocumented_routes,
            "orphaned_specs": orphaned_specs,
            "template_matches": template_matches,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate OpenAPI schema route coverage and implementation parity."
    )
    parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Path to OpenAPI/Swagger specification file (JSON or YAML).",
    )
    parser.add_argument(
        "--code-root",
        type=Path,
        default=Path("."),
        help="Root path containing backend route code (default: current directory).",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.0,
        help="Minimum required coverage percentage (0-100).",
    )
    parser.add_argument(
        "--fail-on-undocumented",
        action="store_true",
        help="Fail if any implemented route is missing from the OpenAPI specification.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format.",
    )

    args = parser.parse_args()

    if not args.spec.is_file():
        print(f"Error: Specification file not found: {args.spec}", file=sys.stderr)
        return 1

    spec_endpoints = parse_openapi_spec(args.spec)
    code_routes = scan_codebase_routes(args.code_root)

    validator = OpenApiCoverageValidator()
    report = validator.compare(spec_endpoints, code_routes)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("OpenAPI Route Coverage & Parity Report")
        print(f"Spec Endpoints: {report['total_spec_endpoints']}")
        print(f"Implemented Routes: {report['total_implemented_routes']}")
        print(f"Coverage: {report['coverage_percentage']}%\n")

        if report["undocumented_routes"]:
            print(f"Undocumented Routes ({len(report['undocumented_routes'])}):")
            for r in report["undocumented_routes"]:
                print(f"  - {r['method']} {r['path']} ({r['file']}:{r['line']})")

        if report["orphaned_specs"]:
            print(f"\nOrphaned Spec Endpoints ({len(report['orphaned_specs'])}):")
            for o in report["orphaned_specs"]:
                print(f"  - {o['method']} {o['path']}")

    if report["coverage_percentage"] < args.min_coverage:
        return 1
    if args.fail_on_undocumented and report["undocumented_routes"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
