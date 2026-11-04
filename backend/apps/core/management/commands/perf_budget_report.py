"""Measure API latency on a fixed dataset and compare it with perf_budget.json.

Usage:
    python manage.py perf_budget_report
    python manage.py perf_budget_report --output report.md --json-output report.json
    python manage.py perf_budget_report --update-budget --reason "why it got slower"
    python manage.py perf_budget_report --update-budget --reason "..." --from-report report.json

By default the command builds a throwaway test database, so it never touches
your development data. The command exits non zero when a route is over budget.
Details: docs/backend/API_PERFORMANCE_BUDGET.md
"""

import json
import platform
from contextlib import contextmanager
from pathlib import Path

import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import (
    override_settings,
    setup_databases,
    setup_test_environment,
    teardown_databases,
    teardown_test_environment,
)

from apps.core import perf_budget as pb
from apps.core import perf_budget_runner as runner

DEFAULT_BUDGET = Path(settings.BASE_DIR) / "perf_budget.json"
DEFAULT_RUNS = 40
DEFAULT_WARMUP = 5

# Keep the measurement repeatable: no read replica routing (it picks a replica
# at random), no random request sampling in PerformanceTrackingMiddleware, and a
# local memory cache so the command never clears a shared Redis. DEBUG is off
# so Django does not keep a log of every query while the clock is running.
_MEASURE_SETTINGS = {
    "DEBUG": False,
    "DATABASE_ROUTERS": [],
    "PERF_TRACK_SAMPLE_RATE": 0,
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
}


class Command(BaseCommand):
    help = (
        "Report API latency percentiles against the budgets in backend/perf_budget.json"
    )

    def add_arguments(self, parser):
        parser.add_argument("--budget", default=str(DEFAULT_BUDGET), help="budget file")
        parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
        parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
        parser.add_argument("--output", help="also write the markdown report here")
        parser.add_argument("--json-output", help="write the raw measurements here")
        parser.add_argument(
            "--from-report",
            help="use measurements from a --json-output file instead of measuring "
            "(handy for raising a budget with the numbers the CI job produced)",
        )
        parser.add_argument(
            "--update-budget",
            action="store_true",
            help="raise the budget of routes that are over it (or have none) and "
            "write the budget file. Needs --reason. Never lowers a budget.",
        )
        parser.add_argument("--reason", help="why the budget is being raised")
        parser.add_argument(
            "--headroom-pct",
            type=float,
            default=pb.DEFAULT_HEADROOM_PCT,
            help="extra room on top of the measured p95 when raising a budget",
        )
        parser.add_argument(
            "--current-db",
            action="store_true",
            help="seed into the configured database instead of a throwaway one "
            "(the tests use this, do not point it at data you care about)",
        )

    def handle(self, *args, **options):
        runs, warmup = options["runs"], options["warmup"]
        if runs < 1 or warmup < 0:
            raise CommandError("--runs must be at least 1 and --warmup at least 0")
        if options["update_budget"] and not (options["reason"] or "").strip():
            raise CommandError("--update-budget needs --reason")

        budget_path = Path(options["budget"])
        try:
            budget = pb.load_budget(budget_path)
            if options["from_report"]:
                saved = json.loads(Path(options["from_report"]).read_text("utf-8"))
                results = pb.results_from_dict(saved)
                meta = saved.get("meta") or {}
                runs = int(meta.get("runs", runs))
                warmup = int(meta.get("warmup", warmup))
            else:
                results = self._measure(runs, warmup, options["current_db"])
        except (pb.BudgetError, OSError, ValueError) as exc:
            raise CommandError(str(exc))

        rows = pb.compare(results, budget)
        report = pb.render_markdown(
            rows,
            budget.margin_pct,
            runs,
            warmup,
            dataset=runner.DATASET_DESCRIPTION,
        )
        self.stdout.write(report)
        if options["output"]:
            Path(options["output"]).write_text(report, encoding="utf-8")
        if options["json_output"]:
            meta = {
                "runs": runs,
                "warmup": warmup,
                "dataset": runner.DATASET_DESCRIPTION,
                "python": platform.python_version(),
                "django": django.get_version(),
                "database": connection.vendor,
            }
            Path(options["json_output"]).write_text(
                json.dumps(pb.results_to_dict(results, meta), indent=2) + "\n",
                encoding="utf-8",
            )

        if options["update_budget"]:
            try:
                new_budget, changed = pb.update_budget(
                    budget, rows, options["reason"], options["headroom_pct"]
                )
            except pb.BudgetError as exc:
                raise CommandError(str(exc))
            if not changed:
                self.stdout.write("Nothing is over budget, perf_budget.json unchanged.")
                return
            pb.write_budget(budget_path, new_budget)
            self.stdout.write(
                f"Raised the budget of {', '.join(changed)} in {budget_path}. "
                "Commit it with the code change that needs it."
            )
            return

        if pb.has_failures(rows):
            raise CommandError(
                "API performance budget exceeded, see the report above "
                f"({pb.DOC_PATH})."
            )

    def _measure(self, runs, warmup, current_db):
        with override_settings(**_MEASURE_SETTINGS):
            with self._database(current_db):
                context = runner.seed_dataset()
                return runner.measure(context, runs, warmup)

    @contextmanager
    def _database(self, current_db):
        if current_db:
            yield
            return
        setup_test_environment()
        old_config = setup_databases(
            verbosity=0, interactive=False, aliases=["default"], serialized_aliases=[]
        )
        try:
            yield
        finally:
            teardown_databases(old_config, verbosity=0)
            teardown_test_environment()
