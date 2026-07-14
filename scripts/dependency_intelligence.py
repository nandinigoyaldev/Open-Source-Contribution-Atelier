#!/usr/bin/env python3
"""Weekly dependency-update analysis and PR report generator."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

REGISTRY_TIMEOUT = 20
DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)


@dataclass
class Update:
    ecosystem: str
    package: str
    old: str
    new: str
    classification: str
    release_notes: list[str]
    peer_dependency_changes: list[str]
    breaking_changes: list[str]


def http_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "dependency-intelligence-action"},
    )
    with urllib.request.urlopen(request, timeout=REGISTRY_TIMEOUT) as response:
        return json.load(response)


def normalize_version(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"^[\^~<>=v\s]+", "", value)
    value = value.split(" ")[0].split("||")[0].strip()
    return value.rstrip(",")


def classify(old: str, new: str) -> str:
    try:
        old_v = Version(normalize_version(old))
        new_v = Version(normalize_version(new))
    except InvalidVersion:
        return "unknown"
    if new_v.major != old_v.major:
        return "major"
    if new_v.minor != old_v.minor:
        return "minor"
    if new_v.micro != old_v.micro:
        return "patch"
    return "none"


def read_package_json(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for section in DEPENDENCY_SECTIONS:
        for name, version in payload.get(section, {}).items():
            result[name] = str(version)
    return result


def requirement_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        try:
            requirement = Requirement(line)
        except Exception:
            continue
        result[requirement.name] = str(requirement.specifier) or "*"
    return result


def changed_dependencies(before: dict[str, str], after: dict[str, str]) -> Iterable[tuple[str, str, str]]:
    for name in sorted(set(before) & set(after)):
        if before[name] != after[name]:
            yield name, before[name], after[name]


def npm_metadata(package: str, old: str, new: str) -> tuple[list[str], list[str], list[str]]:
    encoded = urllib.parse.quote(package, safe="@")
    try:
        metadata = http_json(f"https://registry.npmjs.org/{encoded}")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ["Release metadata could not be fetched."], [], []

    old_version = normalize_version(old)
    new_version = normalize_version(new)
    latest_meta = metadata.get("versions", {}).get(new_version, {})
    old_meta = metadata.get("versions", {}).get(old_version, {})

    notes: list[str] = []
    repository = latest_meta.get("repository") or metadata.get("repository")
    if isinstance(repository, dict):
        repository = repository.get("url")
    if repository:
        notes.append(f"Upstream repository: {repository}")
    description = latest_meta.get("description") or metadata.get("description")
    if description:
        notes.append(str(description).strip())

    peer_changes: list[str] = []
    old_peers = old_meta.get("peerDependencies", {}) or {}
    new_peers = latest_meta.get("peerDependencies", {}) or {}
    for peer in sorted(set(old_peers) | set(new_peers)):
        old_value = old_peers.get(peer)
        new_value = new_peers.get(peer)
        if old_value != new_value:
            peer_changes.append(f"{peer}: {old_value or '(none)'} → {new_value or '(none)'}")

    breaking: list[str] = []
    if classify(old, new) == "major":
        breaking.append("Major version change; review the upstream migration guide and changelog.")
    if peer_changes:
        breaking.append("Peer dependency requirements changed.")
    return notes[:4], peer_changes, breaking


def pypi_metadata(package: str, old: str, new: str) -> tuple[list[str], list[str], list[str]]:
    try:
        metadata = http_json(f"https://pypi.org/pypi/{urllib.parse.quote(package)}/json")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ["Release metadata could not be fetched."], [], []

    info = metadata.get("info", {})
    notes: list[str] = []
    if info.get("summary"):
        notes.append(str(info["summary"]).strip())
    project_urls = info.get("project_urls") or {}
    changelog = project_urls.get("Changelog") or project_urls.get("Release notes")
    if changelog:
        notes.append(f"Release notes: {changelog}")
    if info.get("home_page"):
        notes.append(f"Homepage: {info['home_page']}")

    breaking = []
    if classify(old, new) == "major":
        breaking.append("Major version change; review deprecations and migration notes.")
    return notes[:4], [], breaking


def build_update(ecosystem: str, package: str, old: str, new: str) -> Update:
    if ecosystem == "npm":
        notes, peers, breaking = npm_metadata(package, old, new)
    else:
        notes, peers, breaking = pypi_metadata(package, old, new)
    return Update(
        ecosystem=ecosystem,
        package=package,
        old=old,
        new=new,
        classification=classify(old, new),
        release_notes=notes,
        peer_dependency_changes=peers,
        breaking_changes=breaking,
    )


def overall_classification(updates: list[Update]) -> str:
    priority = {"none": 0, "unknown": 1, "patch": 2, "minor": 3, "major": 4}
    return max((update.classification for update in updates), key=lambda item: priority[item], default="none")


def markdown_report(updates: list[Update]) -> str:
    overall = overall_classification(updates)
    lines = [
        "## Weekly Dependency Intelligence Report",
        "",
        f"**Overall classification:** `{overall.upper()}`",
        "",
        "This pull request groups the weekly npm and PyPI dependency updates into one reviewable change.",
        "",
        "### Policy",
        "",
        "- **Patch:** eligible for auto-merge after required CI checks pass.",
        "- **Minor:** requires changelog review.",
        "- **Major:** flagged as breaking and assigned to a human reviewer.",
        "",
    ]
    if not updates:
        lines.extend(["No dependency manifest changes were detected.", ""])
        return "\n".join(lines)

    for update in updates:
        badge = "BREAKING" if update.classification == "major" else update.classification.upper()
        lines.extend([
            f"### `{update.package}` ({update.ecosystem})",
            "",
            f"- Upgrade: `{update.old}` → `{update.new}`",
            f"- Classification: **{badge}**",
        ])
        if update.release_notes:
            lines.append("- Release context:")
            lines.extend(f"  - {note}" for note in update.release_notes)
        if update.peer_dependency_changes:
            lines.append("- Peer dependency changes:")
            lines.extend(f"  - `{change}`" for change in update.peer_dependency_changes)
        if update.breaking_changes:
            lines.append("- Breaking-change analysis:")
            lines.extend(f"  - {change}" for change in update.breaking_changes)
        lines.append("")

    lines.extend([
        "### Reviewer checklist",
        "",
        "- [ ] Required CI checks pass.",
        "- [ ] Minor/major changelog notes were reviewed.",
        "- [ ] Major updates were tested against relevant application flows.",
        "- [ ] Removed exports and peer dependency changes were evaluated where applicable.",
        "",
        "Closes #1643",
        "",
    ])
    return "\n".join(lines)


def update_python_requirements(path: Path) -> None:
    original = path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    for raw_line in original:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            output.append(raw_line)
            continue
        try:
            requirement = Requirement(stripped)
        except Exception:
            output.append(raw_line)
            continue
        try:
            metadata = http_json(f"https://pypi.org/pypi/{urllib.parse.quote(requirement.name)}/json")
            versions = []
            for version_text, files in metadata.get("releases", {}).items():
                try:
                    version = Version(version_text)
                except InvalidVersion:
                    continue
                if version.is_prerelease or not files:
                    continue
                if not requirement.specifier or version in requirement.specifier:
                    versions.append(version)
            if not versions:
                output.append(raw_line)
                continue
            latest_allowed = str(max(versions))
            spec = str(requirement.specifier)
            if spec.startswith("=="):
                new_spec = f"=={latest_allowed}"
            elif ">=" in spec:
                parts = [part.strip() for part in spec.split(",")]
                parts = [f">={latest_allowed}" if part.startswith(">=") else part for part in parts]
                new_spec = ",".join(parts)
            else:
                output.append(raw_line)
                continue
            marker = f"; {requirement.marker}" if requirement.marker else ""
            extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
            output.append(f"{requirement.name}{extras}{new_spec}{marker}")
        except (urllib.error.URLError, TimeoutError, ValueError):
            output.append(raw_line)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def command_report(args: argparse.Namespace) -> int:
    updates: list[Update] = []
    npm_pairs = [
        (Path(args.before_root), Path(args.after_root)),
        (Path(args.before_frontend), Path(args.after_frontend)),
    ]
    for before_path, after_path in npm_pairs:
        before = read_package_json(before_path)
        after = read_package_json(after_path)
        updates.extend(build_update("npm", name, old, new) for name, old, new in changed_dependencies(before, after))

    before_python = requirement_map(Path(args.before_python))
    after_python = requirement_map(Path(args.after_python))
    updates.extend(build_update("pypi", name, old, new) for name, old, new in changed_dependencies(before_python, after_python))

    report = markdown_report(updates)
    Path(args.output).write_text(report, encoding="utf-8")
    payload = {
        "overall_classification": overall_classification(updates),
        "updates": [asdict(update) for update in updates],
    }
    Path(args.json_output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(report)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subcommands = root.add_subparsers(dest="command", required=True)

    update_python = subcommands.add_parser("update-python")
    update_python.add_argument("--requirements", required=True)

    report = subcommands.add_parser("report")
    report.add_argument("--before-root", required=True)
    report.add_argument("--after-root", required=True)
    report.add_argument("--before-frontend", required=True)
    report.add_argument("--after-frontend", required=True)
    report.add_argument("--before-python", required=True)
    report.add_argument("--after-python", required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--json-output", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "update-python":
        update_python_requirements(Path(args.requirements))
        return 0
    if args.command == "report":
        return command_report(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
