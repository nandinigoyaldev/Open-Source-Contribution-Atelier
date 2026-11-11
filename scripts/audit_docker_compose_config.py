#!/usr/bin/env python3
"""
Docker Compose service health, port collision, and volume integrity analyzer.

Performs static analysis on docker-compose configuration files:
- Detects host port collisions across services.
- Verifies named volume references match top-level volume declarations.
- Checks stateful/backing services for healthcheck definitions.

Zero external dependencies (uses standard library parser).

Usage:
    python scripts/audit_docker_compose_config.py [COMPOSE_FILES...] [--strict]
"""

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

PORT_LINE_REGEX = re.compile(
    r"""^\s*-\s*['"]?(?:(?:(?P<host_ip>[0-9.]+):)?(?P<host_port>[0-9]+):)?(?P<container_port>[0-9]+)(?:/[a-z0-9]+)?['"]?\s*$"""
)


def parse_port_entry(port_str: str) -> Optional[Tuple[str, int, int]]:
    """
    Parse a Docker compose port mapping string.
    Returns: (host_ip, host_port, container_port) or None if parsing fails.
    """
    match = PORT_LINE_REGEX.match(port_str)
    if not match:
        return None

    host_ip = match.group("host_ip") or "0.0.0.0"
    raw_host_port = match.group("host_port")
    raw_container_port = match.group("container_port")

    if raw_host_port is None:
        # Container port only exposed internally (e.g. "8000")
        return None

    return (host_ip, int(raw_host_port), int(raw_container_port))


def parse_compose_file(filepath: str) -> Dict[str, Any]:
    """
    Parse a Docker Compose file into a simplified representation:
    {
        "services": {
            service_name: {
                "ports": [...],
                "has_healthcheck": bool,
                "volumes": [...],
                "image": str,
            }
        },
        "volumes": set(declared_volume_names)
    }
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    services: Dict[str, Dict[str, Any]] = {}
    declared_volumes: Set[str] = set()

    current_section = None
    current_service = None
    current_subfield = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))

        # Top-level sections (indent 0)
        if indent == 0 and stripped.endswith(":"):
            section_name = stripped[:-1].strip()
            current_section = section_name
            current_service = None
            current_subfield = None
            continue

        if current_section == "services":
            # Service declaration at indent 2
            if indent == 2 and stripped.endswith(":"):
                current_service = stripped[:-1].strip()
                current_subfield = None
                services[current_service] = {
                    "ports": [],
                    "has_healthcheck": False,
                    "volumes": [],
                    "image": "",
                }
                continue

            if current_service and indent == 4:
                if stripped.startswith("image:"):
                    img = stripped.split("image:", 1)[1].strip()
                    services[current_service]["image"] = img
                    current_subfield = None
                elif stripped.startswith("healthcheck:"):
                    services[current_service]["has_healthcheck"] = True
                    current_subfield = "healthcheck"
                elif stripped.endswith(":"):
                    current_subfield = stripped[:-1].strip()
                else:
                    current_subfield = None
                continue

            if current_service and indent >= 6:
                if current_subfield == "ports" and stripped.startswith("-"):
                    port_val = stripped.lstrip("- ").strip()
                    parsed = parse_port_entry(stripped)
                    if parsed:
                        services[current_service]["ports"].append(parsed)
                elif current_subfield == "volumes" and stripped.startswith("-"):
                    vol_val = stripped.lstrip("- ").strip().strip("'\"")
                    services[current_service]["volumes"].append(vol_val)
                elif current_subfield == "healthcheck":
                    services[current_service]["has_healthcheck"] = True

        elif current_section == "volumes":
            if indent == 2 and stripped.endswith(":"):
                vol_name = stripped[:-1].strip()
                declared_volumes.add(vol_name)

    return {
        "services": services,
        "volumes": declared_volumes,
    }


def find_port_collisions(services: Dict[str, Dict[str, Any]]) -> List[str]:
    """Identify instances where different services bind the same host port."""
    collisions = []
    claimed_ports: Dict[Tuple[str, int], str] = {}  # (host_ip, host_port) -> service_name

    for s_name, s_data in sorted(services.items()):
        for host_ip, host_port, _ in s_data.get("ports", []):
            # Check collisions against 0.0.0.0 or exact host_ip
            conflict_service = claimed_ports.get((host_ip, host_port))
            if not conflict_service and host_ip != "0.0.0.0":
                conflict_service = claimed_ports.get(("0.0.0.0", host_port))

            if conflict_service and conflict_service != s_name:
                collisions.append(
                    f"Port conflict on host port {host_port} ({host_ip}): "
                    f"bound by both '{conflict_service}' and '{s_name}'"
                )
            else:
                claimed_ports[(host_ip, host_port)] = s_name

    return collisions


def find_undeclared_named_volumes(
    services: Dict[str, Dict[str, Any]], declared_volumes: Set[str]
) -> List[str]:
    """Detect services using named volumes not declared in the top-level volumes block."""
    issues = []
    for s_name, s_data in sorted(services.items()):
        for vol in s_data.get("volumes", []):
            # Parse source volume name from mount expression: source:target[:mode]
            parts = vol.split(":")
            if not parts:
                continue
            source = parts[0].strip()
            # If source does not start with ./, /, ~, or $, it's a named volume
            if not any(source.startswith(prefix) for prefix in (".", "/", "~", "$")):
                if source not in declared_volumes:
                    issues.append(
                        f"Service '{s_name}' references undeclared named volume '{source}'"
                    )

    return issues


def find_missing_healthchecks(services: Dict[str, Dict[str, Any]]) -> List[str]:
    """Recommend healthcheck configurations for stateful dependencies."""
    warnings = []
    stateful_keywords = ("postgres", "mysql", "redis", "meili", "mongo", "db")

    for s_name, s_data in sorted(services.items()):
        image = s_data.get("image", "").lower()
        name_lower = s_name.lower()
        is_stateful = any(kw in image or kw in name_lower for kw in stateful_keywords)

        if is_stateful and not s_data.get("has_healthcheck"):
            warnings.append(
                f"Stateful service '{s_name}' (image: '{s_data.get('image')}') has no healthcheck configured."
            )

    return warnings


def audit_compose_file(filepath: str) -> Tuple[List[str], List[str], List[str]]:
    """Audit a single docker-compose file."""
    parsed = parse_compose_file(filepath)
    collisions = find_port_collisions(parsed["services"])
    undeclared_vols = find_undeclared_named_volumes(parsed["services"], parsed["volumes"])
    missing_healthchecks = find_missing_healthchecks(parsed["services"])
    return collisions, undeclared_vols, missing_healthchecks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        default=["docker-compose.yml"],
        help="Compose files to audit (default: docker-compose.yml)",
    )
    parser.add_argument("--strict", action="store_true", help="Fail if collisions or undeclared volumes exist")
    args = parser.parse_args()

    total_collisions = 0
    total_undeclared = 0

    for file in args.files:
        if not os.path.exists(file):
            print(f"⚠️  Skipping non-existent file: {file}")
            continue

        print(f"\n🐳 Auditing Docker Compose: '{file}'")
        collisions, undeclared, health_warnings = audit_compose_file(file)

        if collisions:
            total_collisions += len(collisions)
            print("❌ Port Collisions:")
            for c in collisions:
                print(f"  - {c}")
        else:
            print("✅ No host port collisions detected.")

        if undeclared:
            total_undeclared += len(undeclared)
            print("❌ Undeclared Named Volumes:")
            for u in undeclared:
                print(f"  - {u}")
        else:
            print("✅ All named volume mounts are properly declared.")

        if health_warnings:
            print("ℹ️  Healthcheck Recommendations:")
            for hw in health_warnings:
                print(f"  - {hw}")
        else:
            print("✅ Healthcheck definitions present for stateful services.")

    if args.strict and (total_collisions > 0 or total_undeclared > 0):
        print(f"\n❌ Audit failed: {total_collisions} collision(s), {total_undeclared} undeclared volume(s).")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
