"""
CSV data challenge lesson plugin.

Validates a user-submitted CSV document against expected headers,
per-column types, row count bounds, and (optionally) specific cell
values. Scored by percentage of checks passed rather than exact-string
matching, so formatting variation (whitespace, quoting) doesn't
unfairly fail an otherwise-correct submission.
"""

import csv
import io
from typing import Any, Dict, List, Optional

from .plugins import LessonPlugin, registry


_TYPE_COERCERS = {
    "string": str,
    "integer": int,
    "float": float,
}


def _try_coerce(value: str, expected_type: str) -> bool:
    """Return True if value can be coerced to expected_type."""
    coercer = _TYPE_COERCERS.get(expected_type, str)
    if coercer is str:
        return True
    try:
        coercer(value.strip())
        return True
    except (ValueError, TypeError):
        return False


def _parse_csv(text: str) -> List[Dict[str, str]]:
    """Parse CSV text into a list of row dicts keyed by header. Raises csv.Error on malformed input."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise csv.Error("CSV has no header row")
    return list(reader)


class CSVDataChallengePlugin(LessonPlugin):
    """
    Lesson plugin for CSV-writing/data-shaping challenges.

    Expected submission data shape:
    {
        "submitted_csv": "name,age\\nAlice,30\\nBob,25\\n",
        "required_headers": ["name", "age"],
        "column_types": {"age": "integer"},          # optional
        "min_rows": 1,                                # optional
        "max_rows": 100,                               # optional
        "expected_cells": [                            # optional exact checks
            {"row": 0, "column": "name", "value": "Alice"}
        ]
    }
    """

    identifier = "csv_data_challenge"
    version = "1.0"
    name = "CSV Data Challenge"
    description = (
        "Produce a CSV document matching required headers, per-column "
        "types, row count bounds, and specific cell values, scored by "
        "percentage of checks satisfied."
    )

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        submitted = data.get("submitted_csv")
        if not isinstance(submitted, str) or not submitted.strip():
            return False

        required_headers = data.get("required_headers")
        if not isinstance(required_headers, list) or not all(isinstance(h, str) for h in required_headers):
            return False

        for optional_key, expected_kind in (
            ("column_types", dict), ("min_rows", int), ("max_rows", int), ("expected_cells", list)
        ):
            if optional_key in data and not isinstance(data[optional_key], expected_kind):
                return False

        try:
            _parse_csv(submitted)
        except csv.Error:
            return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        try:
            rows = _parse_csv(data["submitted_csv"])
        except csv.Error:
            return 0.0

        actual_headers = set(rows[0].keys()) if rows else set(
            csv.reader(io.StringIO(data["submitted_csv"])).__next__()
        )

        checks_passed = 0
        checks_total = 0

        # Check 1: all required headers present
        required_headers = data["required_headers"]
        checks_total += 1
        if all(h in actual_headers for h in required_headers):
            checks_passed += 1

        # Check 2: row count bounds
        min_rows = data.get("min_rows")
        max_rows = data.get("max_rows")
        if min_rows is not None or max_rows is not None:
            checks_total += 1
            row_count = len(rows)
            lower_ok = min_rows is None or row_count >= min_rows
            upper_ok = max_rows is None or row_count <= max_rows
            if lower_ok and upper_ok:
                checks_passed += 1

        # Check 3: per-column type coercion, checked across all rows
        column_types = data.get("column_types", {})
        for column, expected_type in column_types.items():
            checks_total += 1
            if column not in actual_headers:
                continue
            if all(_try_coerce(row.get(column, ""), expected_type) for row in rows):
                checks_passed += 1

        # Check 4: specific expected cell values
        expected_cells = data.get("expected_cells", [])
        for cell in expected_cells:
            checks_total += 1
            row_idx = cell.get("row")
            column = cell.get("column")
            expected_value = cell.get("value")
            if (
                isinstance(row_idx, int)
                and 0 <= row_idx < len(rows)
                and column in rows[row_idx]
                and rows[row_idx][column].strip() == str(expected_value).strip()
            ):
                checks_passed += 1

        if checks_total == 0:
            return 0.0

        return round((checks_passed / checks_total) * 100.0, 2)


registry.register(CSVDataChallengePlugin)
