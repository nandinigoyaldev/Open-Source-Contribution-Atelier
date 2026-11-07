import json

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.billing.reconciliation import Reconciler, StripeClient


def build_client():
    """Mock mode has no Stripe account to compare with, and tests must not reach one."""
    key = stripe.api_key
    if getattr(settings, "TESTING", False) or not key or key == "sk_test_mock":
        raise CommandError("reconcile_billing needs a real STRIPE_SECRET_KEY.")
    return StripeClient()


class Command(BaseCommand):
    help = (
        "Compare subscriptions and invoices with Stripe and repair what drifted. "
        "Only reports unless --apply is given. Every run leaves an audit event."
    )

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report mismatches. This is the default.",
        )
        mode.add_argument(
            "--apply", action="store_true", help="Repair the mismatches found."
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="How far back to compare invoices and ledger rows (default 30).",
        )
        parser.add_argument(
            "--customer", help="Only check this Stripe customer id (cus_...)."
        )
        parser.add_argument(
            "--json", action="store_true", help="Print the full report as JSON."
        )

    def handle(self, *args, **options):
        if options["days"] <= 0:
            raise CommandError("--days must be greater than 0.")

        run = Reconciler(
            build_client(),
            apply=options["apply"],
            days=options["days"],
            customer=options["customer"],
        ).run()

        if options["json"]:
            self.stdout.write(json.dumps(run.as_dict(), indent=2))
        else:
            self._print(run)

        if run.errors:
            raise CommandError(f"{len(run.errors)} errors, see the report above.")

    def _print(self, run):
        mode = "applying repairs" if run.apply else "dry run, nothing was changed"
        self.stdout.write(f"Reconcile run {run.run_id} ({mode})")
        for item in run.mismatches:
            state = "repaired" if item.repaired else item.note or "not repaired"
            if not item.repairable:
                state = "needs a manual look"
            self.stdout.write(
                f"  {item.kind} {item.customer_id} {item.stripe_id}: "
                f"{json.dumps(item.detail)} [{state}]"
            )
        for error in run.errors:
            self.stdout.write(f"  error {error['customer_id']}: {error['error']}")
        summary = run.summary()
        self.stdout.write(
            f"Checked {summary['checked']} subscriptions: "
            f"{summary['mismatches']} mismatches, {summary['repaired']} repaired, "
            f"{summary['manual']} need a manual look, {summary['errors']} errors."
        )
