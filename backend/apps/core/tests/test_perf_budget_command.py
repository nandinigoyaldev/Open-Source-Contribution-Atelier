"""End to end test of manage.py perf_budget_report on the seeded dataset."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import perf_budget as pb
from apps.core.perf_budget_runner import ROUTES

pytestmark = pytest.mark.django_db


def write_budget(path, p95=100000, queries=10000, margin=25):
    data = {
        "version": 1,
        "margin_pct": margin,
        "routes": {
            route.name: {"p95_ms": p95, "max_queries": queries, "reason": "test"}
            for route in ROUTES
        },
    }
    path.write_text(json.dumps(data))
    return path


def run(budget, *extra):
    out = StringIO()
    call_command(
        "perf_budget_report",
        "--current-db",
        "--runs=3",
        "--warmup=1",
        f"--budget={budget}",
        *extra,
        stdout=out,
    )
    return out.getvalue()


def test_report_on_the_seeded_dataset(tmp_path):
    budget = write_budget(tmp_path / "budget.json")
    report_md = tmp_path / "report.md"
    report_json = tmp_path / "report.json"

    out = run(budget, f"--output={report_md}", f"--json-output={report_json}")

    assert "PASS: every route is within budget" in out
    assert "50 users, 60 lessons" in out
    assert report_md.read_text() == out
    data = json.loads(report_json.read_text())
    assert [r["name"] for r in data["routes"]] == [r.name for r in ROUTES]
    for row in data["routes"]:
        assert row["status_code"] == 200, row
        assert row["runs"] == 3
        assert 0 < row["p50_ms"] <= row["p95_ms"] <= row["p99_ms"]
        assert row["queries"] > 0


def test_query_counts_are_the_same_on_every_run(tmp_path):
    budget = write_budget(tmp_path / "budget.json")
    counts = []
    for i in range(2):
        target = tmp_path / f"run{i}.json"
        run(budget, f"--json-output={target}")
        counts.append(
            {r["name"]: r["queries"] for r in json.loads(target.read_text())["routes"]}
        )
    assert counts[0] == counts[1]


def test_the_dataset_has_the_same_shape_every_time():
    from django.contrib.auth import get_user_model

    from apps.content.models import Lesson
    from apps.core import perf_budget_runner as runner
    from apps.progress.models import LessonProgress, XPEvent

    for _ in range(2):  # seeding again reuses the rows instead of doubling them
        runner.seed_dataset()
        assert (
            get_user_model().objects.filter(username__startswith="perf-budget").count()
            == 50
        )
        assert Lesson.objects.count() == 60
        assert LessonProgress.objects.count() == 150
        assert XPEvent._default_manager.count() == 250


def test_command_fails_when_a_route_is_over_budget(tmp_path):
    budget = write_budget(tmp_path / "budget.json", queries=0)
    out = StringIO()
    with pytest.raises(CommandError, match="budget exceeded"):
        call_command(
            "perf_budget_report",
            "--current-db",
            "--runs=2",
            "--warmup=0",
            f"--budget={budget}",
            stdout=out,
        )
    assert "OVER BUDGET" in out.getvalue()
    assert "What to do" in out.getvalue()


def test_update_budget_needs_a_reason(tmp_path):
    budget = write_budget(tmp_path / "budget.json", queries=0)
    with pytest.raises(CommandError, match="--reason"):
        run(budget, "--update-budget")
    assert json.loads(budget.read_text())["routes"]["leaderboard"]["max_queries"] == 0


def test_update_budget_raises_it_and_the_next_run_passes(tmp_path):
    budget = write_budget(tmp_path / "budget.json", queries=0)

    out = run(budget, "--update-budget", "--reason=leaderboard now joins profiles")

    assert "Raised the budget of" in out
    updated = pb.load_budget(budget)
    assert all(entry.max_queries > 0 for entry in updated.routes.values())
    assert all(
        entry.reason == "leaderboard now joins profiles"
        for entry in updated.routes.values()
    )
    assert "PASS" in run(budget)


def test_update_budget_from_a_ci_report(tmp_path):
    budget = write_budget(tmp_path / "budget.json", p95=1000, queries=10000)
    report = tmp_path / "ci.json"
    ci = pb.results_to_dict(
        [
            pb.RouteResult(
                "leaderboard", "/api/leaderboard/", 200, 40, 90, 3000, 3100, 5
            )
        ],
        {},
    )
    report.write_text(json.dumps(ci))

    call_command(
        "perf_budget_report",
        f"--budget={budget}",
        f"--from-report={report}",
        "--update-budget",
        "--reason=slow CI runner",
        stdout=StringIO(),
    )

    entry = pb.load_budget(budget).routes["leaderboard"]
    assert entry.p95_ms == 3600  # 3000 plus the default 20% headroom
    assert entry.reason == "slow CI runner"


def test_missing_budget_file_is_a_clear_error(tmp_path):
    with pytest.raises(CommandError, match="cannot read budget file"):
        run(tmp_path / "missing.json")
