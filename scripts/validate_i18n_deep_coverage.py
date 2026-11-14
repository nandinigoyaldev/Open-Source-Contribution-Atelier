#!/usr/bin/env python3
"""
Internationalization (i18n) nested key coverage and translation validator.

Validates locale translation dictionaries against the base locale:
- Recursively flattens and verifies complete nested key coverage.
- Detects untranslated empty strings or whitespace values.
- Checks placeholder parameter consistency (e.g., {{count}} or {username}).

Usage:
    python scripts/validate_i18n_deep_coverage.py [--locales-dir DIR] [--base en] [--strict]
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Set, Tuple

PLACEHOLDER_REGEX = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}|\{([a-zA-Z0-9_]+)\}")


def flatten_keys(data: Any, prefix: str = "") -> Dict[str, str]:
    """
    Recursively flatten nested dictionary into dot-separated keys:
    { "a": { "b": "hello" } } -> { "a.b": "hello" }
    """
    flattened: Dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                flattened.update(flatten_keys(v, full_key))
            elif isinstance(v, str):
                flattened[full_key] = v
            else:
                flattened[full_key] = str(v)
    return flattened


def extract_placeholders(text: str) -> Set[str]:
    """Extract interpolation placeholder tokens from string."""
    tokens = set()
    for match in PLACEHOLDER_REGEX.finditer(text):
        token = match.group(1) or match.group(2)
        if token:
            tokens.add(token)
    return tokens


def load_locale_translations(locale_dir: str) -> Dict[str, str]:
    """Load and merge all JSON translation files in a locale directory."""
    merged: Dict[str, str] = {}
    if not os.path.isdir(locale_dir):
        return merged

    for root, _, files in os.walk(locale_dir):
        for f in sorted(files):
            if f.endswith(".json"):
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        merged.update(flatten_keys(data))
                except Exception as e:
                    print(f"⚠️  Error reading {fpath}: {e}")

    return merged


def compare_locale(
    base_translations: Dict[str, str],
    target_translations: Dict[str, str],
    locale_name: str,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Compare a target locale's translations against the base reference dictionary.
    Returns:
        missing_keys: keys in base but absent in target
        extra_keys: keys in target but absent in base
        empty_values: keys with empty or whitespace-only translation
        mismatched_placeholders: keys where placeholder variables do not match
    """
    missing_keys = []
    extra_keys = []
    empty_values = []
    mismatched_placeholders = []

    base_keys = set(base_translations.keys())
    target_keys = set(target_translations.keys())

    for k in sorted(base_keys - target_keys):
        missing_keys.append(f"Missing key in [{locale_name}]: '{k}'")

    for k in sorted(target_keys - base_keys):
        extra_keys.append(f"Extraneous key in [{locale_name}]: '{k}'")

    for k in sorted(target_keys):
        val = target_translations[k]
        if not val or not val.strip():
            empty_values.append(f"Empty translation in [{locale_name}]: '{k}'")

    for k in sorted(base_keys.intersection(target_keys)):
        val = target_translations[k]
        if not val or not val.strip():
            continue

        base_tokens = extract_placeholders(base_translations[k])
        target_tokens = extract_placeholders(val)
        if base_tokens != target_tokens:
            missing_tokens = base_tokens - target_tokens
            extra_tokens = target_tokens - base_tokens
            details = []
            if missing_tokens:
                details.append(f"missing: {sorted(missing_tokens)}")
            if extra_tokens:
                details.append(f"extra: {sorted(extra_tokens)}")
            mismatched_placeholders.append(
                f"Placeholder mismatch in [{locale_name}] for '{k}': {', '.join(details)}"
            )

    return missing_keys, extra_keys, empty_values, mismatched_placeholders


def validate_all_locales(
    locales_dir: str = "frontend/src/locales",
    base_locale: str = "en",
) -> Tuple[int, Dict[str, Dict[str, List[str]]]]:
    """Scan all locale subdirectories against base locale."""
    results: Dict[str, Dict[str, List[str]]] = {}
    base_path = os.path.join(locales_dir, base_locale)

    if not os.path.exists(base_path):
        print(f"❌ Base locale directory does not exist: {base_path}")
        return 1, results

    base_translations = load_locale_translations(base_path)
    total_issues = 0

    locale_dirs = [
        d for d in os.listdir(locales_dir)
        if os.path.isdir(os.path.join(locales_dir, d)) and d != base_locale
    ]

    for loc in sorted(locale_dirs):
        loc_path = os.path.join(locales_dir, loc)
        target_translations = load_locale_translations(loc_path)
        missing, extra, empty, mismatches = compare_locale(
            base_translations, target_translations, loc
        )

        issue_count = len(missing) + len(empty) + len(mismatches)
        total_issues += issue_count

        results[loc] = {
            "missing": missing,
            "extra": extra,
            "empty": empty,
            "mismatches": mismatches,
        }

    return total_issues, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locales-dir",
        default="frontend/src/locales",
        help="Path to locales directory (default: frontend/src/locales)",
    )
    parser.add_argument(
        "--base",
        default="en",
        help="Base locale name (default: en)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if missing keys, empty values, or placeholder mismatches are detected",
    )
    args = parser.parse_args()

    total_issues, results = validate_all_locales(args.locales_dir, args.base)

    print(f"🌐 Internationalization (i18n) Validator: scanning '{args.locales_dir}' (base: {args.base})")

    for loc, issues in sorted(results.items()):
        print(f"\nLocale [{loc}]:")
        if not (issues["missing"] or issues["empty"] or issues["mismatches"] or issues["extra"]):
            print("  ✅ 100% key parity and placeholder alignment with base.")
            continue

        for m in issues["missing"]:
            print(f"  ❌ {m}")
        for em in issues["empty"]:
            print(f"  ⚠️  {em}")
        for mm in issues["mismatches"]:
            print(f"  ⚠️  {mm}")
        for ex in issues["extra"]:
            print(f"  ℹ️  {ex}")

    if total_issues > 0 and args.strict:
        print(f"\n❌ Validation failed: {total_issues} issue(s) detected across locales.")
        return 1

    print("\n✅ i18n validation check finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
