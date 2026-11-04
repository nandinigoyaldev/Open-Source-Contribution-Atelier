"""Unit tests for the percentile, comparison and budget file logic."""

import json
from pathlib import Path
from typing import Optional

import pytest

from apps.core import perf_budget as pb


def result(name="r", p95=100.0, queries=5, status=200, path="/x/"):
    return pb.RouteResult(
        name=name,
        path=path,
        status_code=status,
        runs=40,
        p50_ms=p95 / 2,
        p95_ms=p95,
        p99_ms=p95 * 1.1,
        queries=queries,
    )


def make_budget(routes=None, margin=25.0, **more):
    """make_budget(r=(100, 5)) -> a budget with r at p95 100 ms and 5 queries."""
    both = {**(routes or {}), **more}
    return pb.Budget(
        margin,
        {
            name: pb.RouteBudget(float(p95), q, "because")
            for name, (p95, q) in both.items()
        },
    )


# -- percentile ------------------------------------------------------------


def test_percentile_nearest_rank():
    values = list(range(1, 101))
    assert pb.percentile(values, 50) == 50
    assert pb.percentile(values, 95) == 95
    assert pb.percentile(values, 99) == 99
    assert pb.percentile(values, 100) == 100


def test_percentile_does_not_need_sorted_input_and_returns_a_sample():
    values = [9.0, 1.0, 5.0, 3.0, 7.0]
    assert pb.percentile(values, 50) == 5.0
    assert pb.percentile(values, 95) == 9.0
    assert pb.percentile(values, 1) == 1.0


def test_percentile_single_value():
    assert pb.percentile([4.2], 99) == 4.2


def test_percentile_with_forty_samples_p99_is_the_slowest():
    values = [float(i) for i in range(40)]
    assert pb.percentile(values, 99) == 39.0
    assert pb.percentile(values, 95) == 37.0


@pytest.mark.parametrize("pct", [0, -1, 101])
def test_percentile_rejects_bad_pct(pct):
    with pytest.raises(ValueError):
        pb.percentile([1.0], pct)


def test_percentile_rejects_empty():
    with pytest.raises(ValueError):
        pb.percentile([], 50)


def test_summarize_takes_the_highest_query_count():
    res = pb.summarize("a", "/a/", 200, [3.0, 1.0, 2.0], [4, 6, 5])
    assert (res.runs, res.p50_ms, res.queries) == (3, 2.0, 6)


# -- compare ---------------------------------------------------------------


def status_of(rows, name):
    return next(r.status for r in rows if r.name == name)


def test_within_budget_is_ok_and_has_no_advice():
    rows = pb.compare([result("a", p95=90)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_OK
    assert rows[0].advice == ""
    assert not pb.has_failures(rows)


def test_over_budget_inside_margin_is_review_not_failure():
    rows = pb.compare([result("a", p95=120)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_REVIEW
    assert not pb.has_failures(rows)


def test_exactly_at_the_margin_limit_still_passes():
    rows = pb.compare([result("a", p95=125)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_REVIEW


def test_over_the_margin_fails_with_actionable_advice():
    rows = pb.compare([result("a", p95=130)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_FAIL
    assert pb.has_failures(rows)
    advice = rows[0].advice
    assert "30% over" in advice
    assert "--update-budget" in advice
    assert pb.DOC_PATH in advice


def test_margin_comes_from_the_budget_file():
    rows = pb.compare([result("a", p95=130)], make_budget({"a": (100, 5)}, margin=50))
    assert rows[0].status == pb.STATUS_REVIEW


def test_one_extra_query_fails_even_when_latency_is_fine():
    rows = pb.compare([result("a", p95=10, queries=6)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_FAIL
    assert "6 queries" in rows[0].advice
    assert "select_related" in rows[0].advice


def test_fewer_queries_than_budget_is_fine():
    rows = pb.compare([result("a", queries=2)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_OK


def test_route_without_budget_fails():
    rows = pb.compare([result("new")], make_budget(a=(100, 5)))
    assert status_of(rows, "new") == pb.STATUS_UNBUDGETED
    assert pb.has_failures(rows)


def test_unexpected_http_status_is_an_error_not_a_latency_number():
    rows = pb.compare([result("a", p95=1, status=500)], make_budget(a=(100, 5)))
    assert rows[0].status == pb.STATUS_ERROR
    assert "HTTP 500" in rows[0].advice


def test_budget_entry_without_a_measurement_is_stale_and_does_not_fail():
    rows = pb.compare([result("a")], make_budget(a=(100, 5), gone=(10, 1)))
    assert status_of(rows, "gone") == pb.STATUS_STALE
    assert not pb.has_failures(rows)


def test_rows_are_sorted_worst_first_and_the_order_is_stable():
    results = [
        result("fine", p95=50),
        result("slow", p95=200),
        result("meh", p95=120),
        result("slower", p95=400),
        result("also-fine", p95=50),
    ]
    budget = make_budget({r.name: (100, 5) for r in results})
    first = [r.name for r in pb.compare(results, budget)]
    assert first == ["slower", "slow", "meh", "also-fine", "fine"]
    assert [r.name for r in pb.compare(list(reversed(results)), budget)] == first


# -- budget file -----------------------------------------------------------


def good_data():
    return {
        "version": 1,
        "margin_pct": 20,
        "routes": {"a": {"p95_ms": 100, "max_queries": 5, "reason": "baseline"}},
    }


def test_parse_budget_accepts_a_good_file():
    budget = pb.parse_budget(good_data())
    assert budget.margin_pct == 20
    assert budget.routes["a"] == pb.RouteBudget(100.0, 5, "baseline")


def test_margin_defaults_when_missing():
    data = good_data()
    del data["margin_pct"]
    assert pb.parse_budget(data).margin_pct == pb.DEFAULT_MARGIN_PCT


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d.update(version=2), "version"),
        (lambda d: d.update(margin_pct=-1), "margin_pct"),
        (lambda d: d.update(routes={}), "routes"),
        (lambda d: d["routes"]["a"].pop("reason"), "reason"),
        (lambda d: d["routes"]["a"].update(reason="  "), "reason"),
        (lambda d: d["routes"]["a"].update(p95_ms=0), "p95_ms"),
        (lambda d: d["routes"]["a"].update(p95_ms="fast"), "p95_ms"),
        (lambda d: d["routes"]["a"].update(max_queries=-1), "max_queries"),
        (lambda d: d["routes"]["a"].update(max_queries=1.5), "max_queries"),
        (lambda d: d["routes"]["a"].update(max_queries=True), "max_queries"),
    ],
)
def test_parse_budget_rejects_bad_files(mutate, message):
    data = good_data()
    mutate(data)
    with pytest.raises(pb.BudgetError, match=message):
        pb.parse_budget(data)


def test_load_budget_reports_missing_and_broken_files(tmp_path):
    with pytest.raises(pb.BudgetError, match="cannot read"):
        pb.load_budget(tmp_path / "nope.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(pb.BudgetError, match="not valid JSON"):
        pb.load_budget(broken)


def test_write_then_load_roundtrip_is_tidy(tmp_path):
    path = tmp_path / "b.json"
    budget = make_budget(b=(12.5, 2), a=(100, 5))
    pb.write_budget(path, budget)
    text = path.read_text()
    assert text.endswith("\n")
    assert '"p95_ms": 100,' in text  # 100.0 is written as 100
    assert text.index('"a"') < text.index('"b"')  # sorted, so diffs stay small
    assert pb.load_budget(path) == budget


def test_committed_budget_file_is_valid_and_covers_every_measured_route():
    from apps.core.perf_budget_runner import ROUTES

    path = Path(__file__).resolve().parents[3] / "perf_budget.json"
    budget = pb.load_budget(path)
    assert {r.name for r in ROUTES} == set(budget.routes)


# -- update_budget ---------------------------------------------------------


def update(results, budget, reason: Optional[str] = "added a join", **kwargs):
    rows = pb.compare(results, budget)
    return pb.update_budget(budget, rows, reason, **kwargs)


def test_update_needs_a_reason():
    budget = make_budget(a=(100, 5))
    for reason in ("", "   ", None):
        with pytest.raises(pb.BudgetError, match="reason"):
            update([result("a", p95=500)], budget, reason=reason)


def test_update_raises_latency_with_headroom_and_stores_the_reason():
    budget = make_budget(a=(100, 5))
    new, changed = update([result("a", p95=130, queries=5)], budget)
    assert changed == ["a"]
    assert new.routes["a"].p95_ms == 156  # 130 * 1.2
    assert new.routes["a"].max_queries == 5
    assert new.routes["a"].reason == "added a join"


def test_update_raises_queries_to_the_measured_count():
    budget = make_budget(a=(100, 5))
    new, changed = update([result("a", p95=10, queries=9)], budget)
    assert changed == ["a"]
    assert new.routes["a"].p95_ms == 100  # latency was fine, left alone
    assert new.routes["a"].max_queries == 9


def test_update_leaves_routes_within_budget_alone_and_never_lowers():
    budget = make_budget(a=(100, 5), b=(100, 5))
    new, changed = update(
        [result("a", p95=10, queries=1), result("b", p95=300, queries=5)], budget
    )
    assert changed == ["b"]
    assert new.routes["a"] == budget.routes["a"]


def test_update_adds_a_budget_for_a_new_route():
    budget = make_budget(a=(100, 5))
    new, changed = update([result("a"), result("new", p95=40.2, queries=3)], budget)
    assert changed == ["new"]
    assert new.routes["new"] == pb.RouteBudget(49.0, 3, "added a join")


def test_update_ignores_routes_that_returned_an_error():
    budget = make_budget(a=(100, 5))
    new, changed = update([result("a", p95=900, queries=99, status=500)], budget)
    assert changed == []
    assert new == budget


def test_update_does_not_touch_the_input_budget():
    budget = make_budget(a=(100, 5))
    update([result("a", p95=300)], budget)
    assert budget.routes["a"].p95_ms == 100


# -- report ----------------------------------------------------------------


def test_markdown_report_worst_first_with_what_to_do():
    results = [result("fine", p95=50), result("slow", p95=300)]
    rows = pb.compare(results, make_budget(fine=(100, 5), slow=(100, 5)))
    md = pb.render_markdown(rows, 25, runs=40, warmup=5, dataset="tiny")
    assert "FAIL: 1 route(s) over budget" in md
    assert "Dataset: tiny." in md
    assert md.index("`slow`") < md.index("`fine`")
    assert "| `slow` | 150.0 | 300.0 | 330.0 | 100 | 5 | 5 | OVER BUDGET |" in md
    assert "### What to do" in md
    assert "`fine`" not in md.split("### What to do")[1]


def test_markdown_report_passes_cleanly_and_is_deterministic():
    rows = pb.compare([result("a", p95=50)], make_budget(a=(100, 5)))
    first = pb.render_markdown(rows, 25, 40, 5)
    assert "PASS: every route is within budget" in first
    assert "What to do" not in first
    assert first == pb.render_markdown(rows, 25, 40, 5)


def test_markdown_report_flags_review_rows():
    rows = pb.compare([result("a", p95=110)], make_budget(a=(100, 5)))
    md = pb.render_markdown(rows, 25, 40, 5)
    assert "PASS with 1 route(s) to review" in md
    assert "REVIEW" in md


def test_results_json_roundtrip():
    results = [result("a"), result("b", p95=12.3456)]
    data = json.loads(json.dumps(pb.results_to_dict(results, {"runs": 40})))
    back = pb.results_from_dict(data)
    assert [r.name for r in back] == ["a", "b"]
    assert back[1].p95_ms == 12.346


def test_results_from_dict_rejects_junk():
    with pytest.raises(pb.BudgetError):
        pb.results_from_dict({"routes": [{"name": "a"}]})
