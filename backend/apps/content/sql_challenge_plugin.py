"""
SQL challenge lesson plugin.

Runs a user-submitted SQL query against an isolated, per-evaluation
in-memory SQLite database (seeded fresh each time from the lesson's
schema/data definition — never the real application database) and
compares the result set against an expected result. Only SELECT
statements are permitted.
"""

import re
import sqlite3
from typing import Any, Dict, List, Tuple

from .plugins import LessonPlugin, registry


class UnsafeQueryError(Exception):
    """Raised when a submitted query fails the SELECT-only safety check."""


_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "attach", "detach", "pragma", "vacuum", "replace",
)


def _assert_select_only(query: str) -> None:
    """
    Reject anything that isn't a single, read-only SELECT statement.
    Defense in depth: this is a keyword denylist check *in addition to*
    running against an isolated in-memory DB with no real data — either
    layer alone would already prevent damage to real data, but both
    together is the safer posture for executing arbitrary user SQL.
    """
    stripped = query.strip().rstrip(";")

    if ";" in stripped:
        raise UnsafeQueryError("Multiple statements are not allowed")

    if not stripped.lower().lstrip().startswith("select"):
        raise UnsafeQueryError("Only SELECT statements are allowed")

    lowered = stripped.lower()
    for keyword in _FORBIDDEN_KEYWORDS:
        # Word-boundary check to avoid false positives on column/table
        # names that merely contain a forbidden substring.
        if re.search(rf"\b{keyword}\b", lowered):
            raise UnsafeQueryError(f"Forbidden keyword in query: {keyword}")


def _run_query(schema_sql: str, seed_data_sql: str, query: str, timeout_seconds: float = 2.0) -> List[Tuple]:
    """
    Execute a SELECT query against a fresh in-memory SQLite DB seeded
    with the lesson's schema/data. Returns the result rows.
    """
    _assert_select_only(query)

    conn = sqlite3.connect(":memory:")
    try:
        step_budget = [int(timeout_seconds * 200000)]  # rough step-based timeout proxy

        def _progress_handler():
            step_budget[0] -= 1
            return step_budget[0] <= 0  # non-zero return aborts the query

        conn.set_progress_handler(_progress_handler, 1000)

        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        if seed_data_sql:
            cursor.executescript(seed_data_sql)

        cursor.execute(query)
        return cursor.fetchall()
    finally:
        conn.close()


def _normalize_rows(rows: List[Tuple], order_matters: bool) -> List[Tuple]:
    """Normalize row order for comparison when the exercise doesn't require a specific order."""
    if order_matters:
        return rows
    return sorted(rows, key=lambda r: tuple(str(v) for v in r))


class SQLChallengePlugin(LessonPlugin):
    """
    Lesson plugin for SQL-writing challenges.

    Expected submission data shape:
    {
        "query": "SELECT name FROM users WHERE age > 18",
        "schema_sql": "CREATE TABLE users (id INTEGER, name TEXT, age INTEGER);",
        "seed_data_sql": "INSERT INTO users VALUES (1, 'Alice', 20), (2, 'Bob', 15);",
        "expected_result": [["Alice"]],
        "order_matters": false
    }

    `schema_sql`/`seed_data_sql`/`expected_result`/`order_matters` are
    supplied by the lesson definition (not the learner) in the real
    integration — included in submission data here for the plugin to be
    self-contained and independently testable.
    """

    identifier = "sql_challenge"
    version = "1.0"
    name = "SQL Challenge"
    description = (
        "Write a SELECT query producing a specified result set, evaluated "
        "against an isolated in-memory SQLite database seeded per lesson."
    )

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        query = data.get("query")
        if not isinstance(query, str) or not query.strip():
            return False

        for key in ("schema_sql", "seed_data_sql"):
            if key in data and not isinstance(data[key], str):
                return False

        expected_result = data.get("expected_result")
        if not isinstance(expected_result, list):
            return False

        try:
            _assert_select_only(query)
        except UnsafeQueryError:
            return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        query = data["query"]
        schema_sql = data.get("schema_sql", "")
        seed_data_sql = data.get("seed_data_sql", "")
        expected_result = [tuple(row) for row in data["expected_result"]]
        order_matters = bool(data.get("order_matters", False))

        try:
            actual_rows = _run_query(schema_sql, seed_data_sql, query)
        except (UnsafeQueryError, sqlite3.Error):
            return 0.0

        normalized_actual = _normalize_rows(actual_rows, order_matters)
        normalized_expected = _normalize_rows(expected_result, order_matters)

        if normalized_actual == normalized_expected:
            return 100.0

        # Partial credit: same row count but wrong content (right shape,
        # wrong filter/columns) vs. completely wrong row count.
        if len(normalized_actual) == len(normalized_expected) and normalized_expected:
            return 25.0

        return 0.0


registry.register(SQLChallengePlugin)
