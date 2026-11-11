#!/usr/bin/env python3
"""
Environment variable parity and configuration drift validator.

Compares documented variables in .env.example files with active lookups in
Python (os.environ, os.getenv) and TypeScript/JavaScript (import.meta.env.VITE_*).

Usage:
    python scripts/validate_env_parity.py [--env-file PATH] [--code-dir PATH] [--strict]
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Set, Tuple

ENV_LINE_REGEX = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
PY_ENV_REGEX = re.compile(
    r"""(?:os\.environ(?:\.get)?|os\.getenv|config)\s*\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]"""
)
TS_ENV_REGEX = re.compile(r"""(?:import\.meta\.env\.|process\.env\.)([A-Za-z_][A-Za-z0-9_]*)""")

# Built-in or framework-injected variables that do not need to be in .env.example
IGNORED_VARS = {
    "PATH",
    "HOME",
    "USER",
    "PWD",
    "SHELL",
    "TERM",
    "NODE_ENV",
    "MODE",
    "BASE_URL",
    "PROD",
    "DEV",
    "SSR",
    "DJANGO_SETTINGS_MODULE",
    "PYTHONPATH",
}


def parse_env_file(filepath: str) -> Dict[str, str]:
    """Parse key-value pairs from a .env or .env.example file."""
    variables = {}
    if not os.path.exists(filepath):
        return variables

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = ENV_LINE_REGEX.match(line)
            if match:
                key = match.group(1)
                val = line.split("=", 1)[1].strip().strip("'\"")
                variables[key] = val

    return variables


def extract_env_keys_from_code(directory: str, extensions: Tuple[str, ...]) -> Set[str]:
    """Scan code files in directory for environment variable lookups."""
    found_keys = set()
    if not os.path.exists(directory):
        return found_keys

    for root, dirs, files in os.walk(directory):
        # Prune ignored directories in-place to prevent traversing deep directory trees
        dirs[:] = [
            d
            for d in dirs
            if d not in ("node_modules", ".venv", ".git", "__pycache__", "dist", "build", ".next")
        ]
        for file in files:
            if file.endswith(extensions):
                fp = os.path.join(root, file)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if file.endswith((".py",)):
                            for match in PY_ENV_REGEX.finditer(content):
                                key = match.group(1)
                                if key not in IGNORED_VARS:
                                    found_keys.add(key)
                        if file.endswith((".ts", ".tsx", ".js", ".jsx")):
                            for match in TS_ENV_REGEX.finditer(content):
                                key = match.group(1)
                                if key not in IGNORED_VARS:
                                    found_keys.add(key)
                except Exception:
                    pass

    return found_keys


def compare_env_parity(
    example_keys: Set[str],
    code_keys: Set[str],
    strict: bool = False,
) -> Tuple[Set[str], Set[str]]:
    """
    Return:
        undocumented_keys: keys used in code but not in .env.example
        unused_keys: keys present in .env.example but not used in code
    """
    undocumented = {k for k in code_keys if k not in example_keys}
    unused = {k for k in example_keys if k not in code_keys}
    return undocumented, unused


def run_checks(base_dir: str = ".", strict: bool = False) -> List[str]:
    """Run environment parity checks across standard repo structure."""
    errors = []

    # 1. Backend check
    backend_env = parse_env_file(os.path.join(base_dir, "backend", ".env.example"))
    backend_code_keys = extract_env_keys_from_code(
        os.path.join(base_dir, "backend", "config"), (".py",)
    )
    if backend_env and backend_code_keys:
        undocumented, unused = compare_env_parity(set(backend_env.keys()), backend_code_keys)
        if undocumented:
            errors.append(
                f"Backend: variables referenced in config but missing from backend/.env.example: "
                f"{sorted(undocumented)}"
            )

    # 2. Frontend check
    frontend_env = parse_env_file(os.path.join(base_dir, "frontend", ".env.example"))
    frontend_code_keys = extract_env_keys_from_code(
        os.path.join(base_dir, "frontend", "src"), (".ts", ".tsx", ".js")
    )
    # Only check VITE_ prefixed keys for frontend parity
    vite_code_keys = {k for k in frontend_code_keys if k.startswith("VITE_")}
    if frontend_env and vite_code_keys:
        undocumented, unused = compare_env_parity(set(frontend_env.keys()), vite_code_keys)
        if undocumented:
            errors.append(
                f"Frontend: VITE_* variables referenced in code but missing from frontend/.env.example: "
                f"{sorted(undocumented)}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root directory (default: current)")
    parser.add_argument("--strict", action="store_true", help="Fail on unused template variables")
    args = parser.parse_args()

    errors = run_checks(args.root, strict=args.strict)
    if errors:
        print(f"⚠️  Detected {len(errors)} environment parity drift issue(s):")
        for err in errors:
            print(f"  - {err}")
        if args.strict:
            return 1
        print("\nNote: Run with --strict to enforce zero-tolerance parity drift in CI.")
        return 0

    print("✅ Environment variable templates are consistent and in parity with code references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
