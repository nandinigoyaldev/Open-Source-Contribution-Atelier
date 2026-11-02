"""Fail when a pull request adds Pyright errors.

The backend has thousands of existing Pyright errors, so a plain ``pyright`` run can never pass.
This compares the per-file error counts of two ``pyright --outputjson`` reports (the base branch and
the pull request) and fails only for files that got *worse*: more errors than before, or errors in a
new file. Line numbers are ignored, so moving code around does not trigger it.

    pyright --outputjson backend > head.json
    python scripts/ci/pyright_regressions.py base.json head.json [--root <repo root>]

Exit code 0: no file got worse.  1: at least one file did.  2: a report could not be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Iterable, List, Tuple


def relative_name(path: str, root: str = "") -> str:
    """Repo-relative POSIX path, so a report made on another machine or checkout still lines up."""
    text = path.replace("\\", "/")
    if root:
        prefix = root.replace("\\", "/").rstrip("/") + "/"
        if text.startswith(prefix):
            return text[len(prefix) :]
    # A report from a checkout in another directory (a CI worktree): keep from the first backend/ or scripts/.
    for marker in ("backend/", "services/", "scripts/"):
        index = text.find("/" + marker)
        if index != -1:
            return text[index + 1 :]
    return PurePosixPath(PureWindowsPath(text).as_posix()).as_posix()


def error_counts(report: dict, root: str = "") -> Counter:
    """Number of error-severity diagnostics per file in a Pyright JSON report."""
    counts: Counter = Counter()
    for diagnostic in report.get("generalDiagnostics", []):
        if diagnostic.get("severity") != "error":
            continue
        counts[relative_name(diagnostic.get("file", ""), root)] += 1
    return counts


def regressions(base: Counter, head: Counter) -> List[Tuple[str, int, int]]:
    """Files whose error count went up: (file, errors before, errors now), worst first."""
    worse = [
        (name, base.get(name, 0), count)
        for name, count in head.items()
        if count > base.get(name, 0)
    ]
    return sorted(worse, key=lambda item: (item[2] - item[1], item[0]), reverse=True)


def messages_for(
    report: dict, names: Iterable[str], root: str = "", limit: int = 5
) -> Dict[str, List[str]]:
    """A few diagnostics per file, for the failure message."""
    wanted = set(names)
    found: Dict[str, List[str]] = {name: [] for name in wanted}
    for diagnostic in report.get("generalDiagnostics", []):
        if diagnostic.get("severity") != "error":
            continue
        name = relative_name(diagnostic.get("file", ""), root)
        if name in wanted and len(found[name]) < limit:
            line = diagnostic.get("range", {}).get("start", {}).get("line", 0) + 1
            rule = diagnostic.get("rule", "")
            text = " ".join(str(diagnostic.get("message", "")).split())
            found[name].append(
                f"{name}:{line}: {text}" + (f" ({rule})" if rule else "")
            )
    return found


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"Could not read the Pyright report {path}: {error}"
        ) from error
    if not isinstance(data, dict) or "generalDiagnostics" not in data:
        raise SystemExit(
            f"{path} is not a Pyright JSON report (no generalDiagnostics)."
        )
    return data


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base", help="Pyright JSON report for the base branch")
    parser.add_argument("head", help="Pyright JSON report for the pull request")
    parser.add_argument(
        "--root", default="", help="repository root to strip from absolute paths"
    )
    args = parser.parse_args(argv)

    try:
        base_report, head_report = load(args.base), load(args.head)
    except SystemExit as error:
        print(error, file=sys.stderr)
        return 2

    base, head = error_counts(base_report, args.root), error_counts(
        head_report, args.root
    )
    worse = regressions(base, head)
    print(
        f"Pyright errors: {sum(base.values())} on the base branch, {sum(head.values())} in this pull request."
    )
    if not worse:
        print("No file has more Pyright errors than before.")
        return 0

    details = messages_for(head_report, [name for name, _, _ in worse], args.root)
    print("\nThis pull request adds Pyright errors:\n")
    for name, before, now in worse:
        print(f"  {name}: {before} -> {now}")
        for line in details.get(name, []):
            print(f"    {line}")
    print(
        "\nFix the errors above (run `npx pyright backend` locally). Existing errors in other files are "
        "not counted; only files that got worse fail this check."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
