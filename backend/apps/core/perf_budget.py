"""Pure logic for the API latency performance budget report.

Nothing in here touches Django, the database or the clock, so it can be unit
tested directly. ``perf_budget_runner`` produces the measurements and
``manage.py perf_budget_report`` ties the two together.

The budget file is ``backend/perf_budget.json``, see
``docs/backend/API_PERFORMANCE_BUDGET.md`` for the schema and for how to raise
a budget on purpose.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
DEFAULT_MARGIN_PCT = 25.0
DEFAULT_HEADROOM_PCT = 20.0
DOC_PATH = "docs/backend/API_PERFORMANCE_BUDGET.md"

STATUS_OK = "ok"
STATUS_REVIEW = "review"
STATUS_FAIL = "fail"
STATUS_UNBUDGETED = "unbudgeted"
STATUS_ERROR = "error"
STATUS_STALE = "stale"

# Statuses that make the report (and the CI job) fail.
FAILING = frozenset({STATUS_FAIL, STATUS_UNBUDGETED, STATUS_ERROR})

# Worst first when the table is sorted.
_SEVERITY = {
    STATUS_ERROR: 0,
    STATUS_FAIL: 1,
    STATUS_UNBUDGETED: 2,
    STATUS_REVIEW: 3,
    STATUS_STALE: 4,
    STATUS_OK: 5,
}


class BudgetError(ValueError):
    """The budget file is missing, unreadable or does not follow the schema."""


@dataclass(frozen=True)
class RouteResult:
    """What was measured for one route."""

    name: str
    path: str
    status_code: int
    runs: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    queries: int


@dataclass(frozen=True)
class RouteBudget:
    p95_ms: float
    max_queries: int
    reason: str


@dataclass(frozen=True)
class Budget:
    margin_pct: float
    routes: Dict[str, RouteBudget]


@dataclass(frozen=True)
class Comparison:
    """One row of the report: a measurement next to its budget."""

    result: Optional[RouteResult]
    name: str
    budget: Optional[RouteBudget]
    status: str
    advice: str

    @property
    def over_pct(self) -> Optional[float]:
        if self.result is None or self.budget is None:
            return None
        return (self.result.p95_ms / self.budget.p95_ms - 1) * 100


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile.

    Always returns one of the input values (no interpolation), so the same
    samples give the same answer on every Python version. With 40 samples p99
    is the slowest one, which is what you want from a worst case number.
    """
    if not values:
        raise ValueError("percentile of an empty list")
    if not 0 < pct <= 100:
        raise ValueError("pct must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[rank - 1]


def summarize(
    name: str,
    path: str,
    status_code: int,
    timings_ms: Sequence[float],
    queries: Sequence[int],
) -> RouteResult:
    """Turn the raw per run numbers of one route into a RouteResult."""
    return RouteResult(
        name=name,
        path=path,
        status_code=status_code,
        runs=len(timings_ms),
        p50_ms=percentile(timings_ms, 50),
        p95_ms=percentile(timings_ms, 95),
        p99_ms=percentile(timings_ms, 99),
        # The dataset is fixed, so this should not vary between runs. If it
        # does (a cache warming up, say) the highest value is the safe one.
        queries=max(queries),
    )


# --------------------------------------------------------------------------
# Budget file
# --------------------------------------------------------------------------


def parse_budget(data: Any) -> Budget:
    """Validate the parsed JSON of a budget file."""
    if not isinstance(data, dict):
        raise BudgetError("budget file must contain a JSON object")
    if data.get("version") != SCHEMA_VERSION:
        raise BudgetError(f"unsupported budget version, expected {SCHEMA_VERSION}")
    margin = _number(data.get("margin_pct", DEFAULT_MARGIN_PCT))
    if margin is None or margin < 0:
        raise BudgetError("margin_pct must be a number >= 0")
    raw_routes = data.get("routes")
    if not isinstance(raw_routes, dict) or not raw_routes:
        raise BudgetError("routes must be a non-empty object")

    routes: Dict[str, RouteBudget] = {}
    for name, entry in raw_routes.items():
        if not isinstance(entry, dict):
            raise BudgetError(f"routes.{name} must be an object")
        p95 = _number(entry.get("p95_ms"))
        queries = entry.get("max_queries")
        reason = entry.get("reason")
        if p95 is None or p95 <= 0:
            raise BudgetError(f"routes.{name}.p95_ms must be a number > 0")
        if isinstance(queries, bool) or not isinstance(queries, int) or queries < 0:
            raise BudgetError(f"routes.{name}.max_queries must be an integer >= 0")
        if not isinstance(reason, str) or not reason.strip():
            raise BudgetError(
                f"routes.{name}.reason is required: say why the budget is what it is"
            )
        routes[name] = RouteBudget(p95, queries, reason.strip())
    return Budget(margin, routes)


def load_budget(path: Path) -> Budget:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise BudgetError(f"cannot read budget file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BudgetError(f"budget file {path} is not valid JSON: {exc}") from exc
    return parse_budget(data)


def budget_to_dict(budget: Budget) -> Dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "margin_pct": _plain(budget.margin_pct),
        "routes": {
            name: {
                "p95_ms": _plain(entry.p95_ms),
                "max_queries": entry.max_queries,
                "reason": entry.reason,
            }
            for name, entry in sorted(budget.routes.items())
        },
    }


def write_budget(path: Path, budget: Budget) -> None:
    text = json.dumps(budget_to_dict(budget), indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------


def compare(
    results: Sequence[RouteResult],
    budget: Budget,
    expected_status: int = 200,
) -> List[Comparison]:
    """Compare every measurement with its budget, worst rows first.

    Rules, in this order for each route:

    * the route did not answer ``expected_status``: ``error``
    * the route has no budget entry: ``unbudgeted`` (add one, with a reason)
    * query count above ``max_queries``: ``fail``. The dataset is fixed, so the
      count is exact and gets no margin.
    * p95 above ``p95_ms`` plus ``margin_pct``: ``fail``
    * p95 above ``p95_ms`` but inside the margin: ``review`` (reported, does
      not fail, this is the CI noise zone)
    * otherwise ``ok``

    A budget entry that no route measures any more is listed as ``stale``.
    """
    rows: List[Comparison] = []
    measured = set()
    for res in results:
        measured.add(res.name)
        entry = budget.routes.get(res.name)
        rows.append(_compare_one(res, entry, budget.margin_pct, expected_status))
    for name, entry in budget.routes.items():
        if name not in measured:
            rows.append(
                Comparison(
                    result=None,
                    name=name,
                    budget=entry,
                    status=STATUS_STALE,
                    advice=(
                        f"`{name}` has a budget but is no longer measured. Remove it "
                        "from perf_budget.json if the route was dropped on purpose."
                    ),
                )
            )
    rows.sort(key=_sort_key)
    return rows


def _compare_one(
    res: RouteResult,
    entry: Optional[RouteBudget],
    margin_pct: float,
    expected_status: int,
) -> Comparison:
    name = res.name
    if res.status_code != expected_status:
        return Comparison(
            res,
            name,
            entry,
            STATUS_ERROR,
            f"`{name}` ({res.path}) answered HTTP {res.status_code}, expected "
            f"{expected_status}. A failing route is not a latency result: fix the "
            "route or the seeded dataset first.",
        )
    if entry is None:
        return Comparison(
            res,
            name,
            None,
            STATUS_UNBUDGETED,
            f"`{name}` has no budget yet (measured p95 {res.p95_ms:.1f} ms, "
            f"{res.queries} queries). Add it with "
            '`python manage.py perf_budget_report --update-budget --reason "..."`.',
        )

    limit_ms = entry.p95_ms * (1 + margin_pct / 100)
    over_pct = (res.p95_ms / entry.p95_ms - 1) * 100

    if res.queries > entry.max_queries:
        return Comparison(
            res,
            name,
            entry,
            STATUS_FAIL,
            f"`{name}` now runs {res.queries} queries, budget is "
            f"{entry.max_queries}. Look for a new query or a missing "
            "`select_related` / `prefetch_related` in the view, serializer or "
            "queryset you changed. If the extra queries are intended, "
            f"{_how_to_raise(name)}",
        )
    if res.p95_ms > limit_ms:
        return Comparison(
            res,
            name,
            entry,
            STATUS_FAIL,
            f"`{name}` p95 is {res.p95_ms:.1f} ms, {over_pct:.0f}% over its "
            f"{entry.p95_ms:g} ms budget (fails above {limit_ms:.1f} ms). Check "
            "what changed in this route's view, serializer, queryset or "
            "middleware, then re-run `python manage.py perf_budget_report` "
            f"locally to confirm. If the slowdown is intended, {_how_to_raise(name)}",
        )
    if res.p95_ms > entry.p95_ms:
        return Comparison(
            res,
            name,
            entry,
            STATUS_REVIEW,
            f"`{name}` p95 is {res.p95_ms:.1f} ms, {over_pct:.0f}% over its "
            f"{entry.p95_ms:g} ms budget but inside the {margin_pct:g}% margin, so "
            "it does not fail. Re-run the job; if it stays over, treat it as a "
            "real slowdown.",
        )
    return Comparison(res, name, entry, STATUS_OK, "")


def _how_to_raise(name: str) -> str:
    return (
        "raise the budget in this PR with "
        '`python manage.py perf_budget_report --update-budget --reason "..."` '
        f"and explain it in the PR description ({DOC_PATH})."
    )


def _sort_key(row: Comparison):
    over = row.over_pct
    return (_SEVERITY[row.status], -(over if over is not None else 0.0), row.name)


def has_failures(rows: Sequence[Comparison]) -> bool:
    return any(row.status in FAILING for row in rows)


# --------------------------------------------------------------------------
# Updating a budget on purpose
# --------------------------------------------------------------------------


def update_budget(
    budget: Budget,
    rows: Sequence[Comparison],
    reason: Optional[str],
    headroom_pct: float = DEFAULT_HEADROOM_PCT,
) -> Tuple[Budget, List[str]]:
    """Raise the budget of every route that is over it, or has none.

    * latency: new ``p95_ms`` is the measured p95 plus ``headroom_pct``, rounded
      up to a whole millisecond, and only if the route was over its p95 budget
    * queries: new ``max_queries`` is the measured count, only if it went up
    * routes with no entry get both values

    It never lowers a budget (edit the file by hand for that) and leaves routes
    that are within budget alone. ``reason`` is required and replaces the reason
    of every entry that changed.
    """
    reason = (reason or "").strip()
    if not reason:
        raise BudgetError("--reason is required when updating the budget")

    routes = dict(budget.routes)
    changed: List[str] = []
    for row in rows:
        res = row.result
        if res is None or row.status in (STATUS_OK, STATUS_STALE, STATUS_ERROR):
            continue
        old = routes.get(row.name)
        new_p95 = math.ceil(res.p95_ms * (1 + headroom_pct / 100))
        if old is None:
            routes[row.name] = RouteBudget(float(new_p95), res.queries, reason)
            changed.append(row.name)
            continue
        p95 = float(new_p95) if res.p95_ms > old.p95_ms else old.p95_ms
        queries = max(old.max_queries, res.queries)
        if p95 != old.p95_ms or queries != old.max_queries:
            routes[row.name] = RouteBudget(p95, queries, reason)
            changed.append(row.name)
    return Budget(budget.margin_pct, routes), changed


# --------------------------------------------------------------------------
# Report output
# --------------------------------------------------------------------------


def render_markdown(
    rows: Sequence[Comparison],
    margin_pct: float,
    runs: int,
    warmup: int,
    dataset: str = "",
) -> str:
    """Markdown report. No timestamps, so equal numbers give an equal report."""
    failing = [r for r in rows if r.status in FAILING]
    review = [r for r in rows if r.status == STATUS_REVIEW]

    if failing:
        verdict = f"FAIL: {len(failing)} route(s) over budget"
    elif review:
        verdict = f"PASS with {len(review)} route(s) to review"
    else:
        verdict = "PASS: every route is within budget"

    lines = [
        "## API performance budget report",
        "",
        f"**{verdict}**",
        "",
        f"{runs} timed requests per route after {warmup} warmup requests, "
        f"latency fails {margin_pct:g}% above the p95 budget, query count has no margin."
        + (f" Dataset: {dataset}." if dataset else ""),
        "",
        "| Route | p50 ms | p95 ms | p99 ms | p95 budget ms | Queries | Query budget | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        res, bud = row.result, row.budget
        lines.append(
            "| `{name}` | {p50} | {p95} | {p99} | {bms} | {q} | {bq} | {st} |".format(
                name=row.name,
                p50=f"{res.p50_ms:.1f}" if res else "-",
                p95=f"{res.p95_ms:.1f}" if res else "-",
                p99=f"{res.p99_ms:.1f}" if res else "-",
                bms=f"{bud.p95_ms:g}" if bud else "-",
                q=res.queries if res else "-",
                bq=bud.max_queries if bud else "-",
                st=_status_label(row),
            )
        )

    todo = [r for r in rows if r.advice]
    if todo:
        lines += ["", "### What to do", ""]
        for row in todo:
            lines.append(f"- **{_status_label(row)}** {row.advice}")
    lines.append("")
    return "\n".join(lines)


def _status_label(row: Comparison) -> str:
    return {
        STATUS_OK: "ok",
        STATUS_REVIEW: "REVIEW",
        STATUS_FAIL: "OVER BUDGET",
        STATUS_UNBUDGETED: "NO BUDGET",
        STATUS_ERROR: "ERROR",
        STATUS_STALE: "STALE",
    }[row.status]


def results_to_dict(
    results: Sequence[RouteResult], meta: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "meta": meta,
        "routes": [
            {
                "name": r.name,
                "path": r.path,
                "status_code": r.status_code,
                "runs": r.runs,
                "p50_ms": round(r.p50_ms, 3),
                "p95_ms": round(r.p95_ms, 3),
                "p99_ms": round(r.p99_ms, 3),
                "queries": r.queries,
            }
            for r in results
        ],
    }


def results_from_dict(data: Any) -> List[RouteResult]:
    try:
        return [
            RouteResult(
                name=str(item["name"]),
                path=str(item["path"]),
                status_code=int(item["status_code"]),
                runs=int(item["runs"]),
                p50_ms=float(item["p50_ms"]),
                p95_ms=float(item["p95_ms"]),
                p99_ms=float(item["p99_ms"]),
                queries=int(item["queries"]),
            )
            for item in data["routes"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise BudgetError(f"not a perf budget report json: {exc}") from exc


def _number(value: Any) -> Optional[float]:
    """The value as a float, or None if it is not a JSON number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _plain(value: float):
    """12.0 -> 12 so the JSON file stays tidy."""
    return int(value) if float(value).is_integer() else value
