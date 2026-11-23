import json

from django.core.management.base import BaseCommand, CommandError

from apps.notifications.outbox import reconcile, requeue_dead


class Command(BaseCommand):
    help = (
        "Report the state of the notification outbox: backlog and its age, rows stuck with an "
        "expired lease, permanently failed (dead) rows, and dispatched rows whose ledger "
        "deliveries failed. Exits with an error when --fail-on-dead or --max-age is exceeded, so "
        "it can run from cron or a health check."
    )

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Print JSON.")
        parser.add_argument(
            "--since-days",
            type=int,
            default=7,
            help="Window for the dispatched-with-failed-deliveries check (default 7).",
        )
        parser.add_argument(
            "--dead-limit",
            type=int,
            default=20,
            help="How many dead rows to list (default 20).",
        )
        parser.add_argument(
            "--fail-on-dead",
            action="store_true",
            help="Exit with an error if any row is dead.",
        )
        parser.add_argument(
            "--max-age",
            type=float,
            default=None,
            help="Exit with an error if the oldest undispatched row is older than this many seconds.",
        )
        parser.add_argument(
            "--requeue-dead",
            action="store_true",
            help="Give dead rows a fresh set of attempts (all of them, or only those in --id).",
        )
        parser.add_argument(
            "--id",
            type=int,
            action="append",
            dest="ids",
            help="Restrict --requeue-dead to this row id (repeatable).",
        )

    def handle(self, *args, **options):
        if options["requeue_dead"]:
            n = requeue_dead(options["ids"])
            self.stdout.write(f"Requeued {n} dead outbox row(s)")

        report = reconcile(
            since_days=options["since_days"], dead_limit=options["dead_limit"]
        )
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._print(report)

        problems = []
        if options["fail_on_dead"] and report["dead"]:
            problems.append(f"{report['dead']} dead outbox row(s)")
        age = report["oldest_backlog_age_seconds"]
        if (
            options["max_age"] is not None
            and age is not None
            and age > options["max_age"]
        ):
            problems.append(
                f"oldest undispatched row is {age:.0f}s old (limit {options['max_age']:.0f}s)"
            )
        if problems:
            raise CommandError("; ".join(problems))

    def _print(self, report):
        out = self.stdout.write
        out("Notification outbox")
        out(
            f"  pending={report['pending']} processing={report['processing']} "
            f"dispatched={report['dispatched']} dead={report['dead']}"
        )
        age = report["oldest_backlog_age_seconds"]
        out(
            f"  backlog={report['backlog']} overdue={report['overdue']} "
            f"stale_processing={report['stale_processing']} "
            f"oldest_backlog_age={'-' if age is None else f'{age:.0f}s'}"
        )
        dead_age = report["oldest_dead_age_seconds"]
        out(
            f"  oldest_dead_age={'-' if dead_age is None else f'{dead_age:.0f}s'} "
            f"dispatched_with_failed_deliveries={report['dispatched_with_failed_deliveries']}"
        )
        if report["dead_rows"]:
            out("Dead rows:")
            for row in report["dead_rows"]:
                out(
                    f"  #{row['id']} user={row['recipient_id']} type={row['notif_type']} "
                    f"attempts={row['attempts']} {row['error_class']}: {row['last_error'][:120]}"
                )
