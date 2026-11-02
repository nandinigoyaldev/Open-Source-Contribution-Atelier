"""Fail when dependency manifests and their lockfiles disagree.

npm: for each package.json that has a package-lock.json next to it, the dependencies the lockfile
recorded for the root package must match package.json (same names, same version ranges). If they do
not, ``npm ci`` fails in CI or, worse, a developer's ``npm install`` rewrites the lockfile later.

Python: the backend has no real lockfile (``backend/uv.lock`` is an empty stub), so the check is
between the two requirement files: every package in ``requirements-prod.txt`` must also be in
``requirements.txt`` (so tests run against what ships), and an exactly pinned production version
(``==1.2.3``) must satisfy the range in ``requirements.txt``.

    python scripts/ci/check_dependency_drift.py [--root <repo root>]

Exit code 0: consistent.  1: drift found (the message says how to fix each case).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

NPM_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)

# (package.json folder relative to the root, display name)
NPM_PROJECTS = (".", "frontend")


def check_npm_project(directory: Path, display: str) -> List[str]:
    manifest_path, lock_path = (
        directory / "package.json",
        directory / "package-lock.json",
    )
    if not manifest_path.exists():
        return []
    if not lock_path.exists():
        return [
            f"{display}/package.json has no package-lock.json next to it. Run `npm install` in {display}/ and commit the lockfile."
        ]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    root = (lock.get("packages") or {}).get("", {})
    problems: List[str] = []

    for section in NPM_SECTIONS:
        wanted: Dict[str, str] = manifest.get(section) or {}
        locked: Dict[str, str] = root.get(section) or {}
        for name in sorted(set(wanted) | set(locked)):
            if name not in locked:
                problems.append(
                    f"{display}: `{name}` ({section}) is in package.json but not in package-lock.json"
                )
            elif name not in wanted:
                problems.append(
                    f"{display}: `{name}` ({section}) is in package-lock.json but not in package.json"
                )
            elif wanted[name] != locked[name]:
                problems.append(
                    f"{display}: `{name}` ({section}) is `{wanted[name]}` in package.json "
                    f"but `{locked[name]}` in package-lock.json"
                )

    if manifest.get("name") and root.get("name") and manifest["name"] != root["name"]:
        problems.append(
            f"{display}: package name is `{manifest['name']}` in package.json but `{root['name']}` in package-lock.json"
        )
    if problems:
        problems.append(
            f"Fix: run `npm install` in {display}/ and commit package-lock.json (`npm ci` fails while they disagree)."
        )
    return problems


REQUIREMENT_LINE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^#;]*)"
)


def parse_requirements(path: Path) -> Dict[str, str]:
    """{normalised name: version specifier text}, ignoring comments, options and blank lines."""
    found: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        match = REQUIREMENT_LINE.match(stripped)
        if match:
            found[re.sub(r"[-_.]+", "-", match.group(1)).lower()] = match.group(
                3
            ).strip()
    return found


def pin_of(spec: str) -> Optional[str]:
    match = re.fullmatch(r"==\s*([0-9][^\s,]*)", spec.strip())
    return match.group(1) if match else None


def satisfies(version: str, spec: str) -> bool:
    """True when `version` satisfies the specifier text (no specifier means any version)."""
    if not spec.strip():
        return True
    from packaging.specifiers import InvalidSpecifier, SpecifierSet
    from packaging.version import InvalidVersion

    try:
        return SpecifierSet(spec.replace(" ", "")).contains(version, prereleases=True)
    except (InvalidSpecifier, InvalidVersion):
        return True  # something we cannot parse is not drift we can prove


def check_python(root: Path) -> List[str]:
    dev_path, prod_path = (
        root / "backend" / "requirements.txt",
        root / "backend" / "requirements-prod.txt",
    )
    if not dev_path.exists() or not prod_path.exists():
        return []
    dev, prod = parse_requirements(dev_path), parse_requirements(prod_path)
    problems: List[str] = []
    for name, spec in sorted(prod.items()):
        if name not in dev:
            problems.append(
                f"backend: `{name}` is in requirements-prod.txt but not in requirements.txt"
            )
            continue
        pinned = pin_of(spec)
        if pinned and not satisfies(pinned, dev[name]):
            problems.append(
                f"backend: `{name}` is pinned to {pinned} in requirements-prod.txt, "
                f"which does not satisfy `{dev[name]}` in requirements.txt"
            )
    if problems:
        problems.append(
            "Fix: add the package to backend/requirements.txt, or change the production pin so both files agree."
        )
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root", default=".", help="repository root (default: current directory)"
    )
    args = parser.parse_args(argv)
    root = Path(args.root)

    problems: List[str] = []
    for folder in NPM_PROJECTS:
        directory = root if folder == "." else root / folder
        problems += check_npm_project(
            directory, "repository root" if folder == "." else folder
        )
    problems += check_python(root)

    if not problems:
        print("Dependency manifests and lockfiles are consistent.")
        return 0
    print("Dependency drift found:\n")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
