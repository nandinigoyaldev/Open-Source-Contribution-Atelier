import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from io import StringIO
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.admin_events import BILLING_RECONCILE_REPAIR, BILLING_RECONCILE_RUN
from apps.audit.models import AuditEvent
from apps.billing.management.commands.reconcile_billing import build_client
from apps.billing.models import (
    CustomerSubscription,
    Invoice,
    Payment,
    StripeEvent,
    SubscriptionPlan,
)
from apps.billing.reconciliation import StripeClient

Subscriptions: Any = CustomerSubscription._default_manager
Events: Any = StripeEvent._default_manager
Invoices: Any = Invoice._default_manager
Payments: Any = Payment._default_manager
Audits: Any = AuditEvent._default_manager

BUILD_CLIENT = "apps.billing.management.commands.reconcile_billing.build_client"


def remote_subscription(
    subscription_id: str = "sub_rec",
    status: str = "active",
    customer: str = "cus_rec",
    **extra: Any,
) -> Dict[str, Any]:
    return {"id": subscription_id, "customer": customer, "status": status, **extra}


def remote_invoice(
    invoice_id: str = "in_rec", status: str = "paid", customer: str = "cus_rec"
) -> Dict[str, Any]:
    return {
        "id": invoice_id,
        "customer": customer,
        "status": status,
        "amount_paid": 2000,
        "currency": "usd",
        "charge": f"ch_{invoice_id}",
    }


class FakeStripe:
    """Stands in for StripeClient, so nothing here can reach Stripe."""

    def __init__(
        self,
        subscriptions: Optional[List[Dict[str, Any]]] = None,
        invoices: Optional[List[Dict[str, Any]]] = None,
        failing_customers: Optional[List[str]] = None,
    ):
        self.subscriptions = subscriptions or []
        self.invoice_rows = invoices or []
        self.failing_customers = failing_customers or []
        self.invoice_since: Any = None

    def subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        for item in self.subscriptions:
            if item["id"] == subscription_id:
                return item
        return None

    def customer_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        return [i for i in self.subscriptions if i["customer"] == customer_id]

    def invoices(self, customer_id: str, since: Any) -> List[Dict[str, Any]]:
        if customer_id in self.failing_customers:
            raise stripe.APIConnectionError("Stripe is unreachable")
        self.invoice_since = since
        return [i for i in self.invoice_rows if i["customer"] == customer_id]


def reconcile(fake: FakeStripe, *args: str) -> str:
    out = StringIO()
    with patch(BUILD_CLIENT, return_value=fake):
        call_command("reconcile_billing", *args, stdout=out)
    return out.getvalue()


def audit_events(operation: str) -> List[Any]:
    return [
        event for event in Audits.all() if event.extra.get("operation") == operation
    ]


class ReconcileTestCase(TestCase):
    def setUp(self) -> None:
        self.user: Any = get_user_model()._default_manager.create_user(
            username="reconcile-user",
            email="reconcile@example.com",
            password="test-password",
        )
        self.pro: Any = SubscriptionPlan._default_manager.create(
            name="Pro", stripe_price_id="price_pro", price=20
        )
        self.sub: Any = Subscriptions.create(
            user=self.user,
            stripe_customer_id="cus_rec",
            stripe_subscription_id="sub_rec",
            plan=self.pro,
            active=True,
            status="active",
        )


class DryRunTests(ReconcileTestCase):
    def test_default_run_reports_and_changes_no_billing_rows(self) -> None:
        fake = FakeStripe(
            subscriptions=[remote_subscription(status="canceled")],
            invoices=[remote_invoice()],
        )

        output = reconcile(fake)

        self.assertIn("dry run", output)
        self.assertIn("subscription_state", output)
        self.assertIn("invoice_missing", output)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(self.sub.status, "active")
        self.assertIsNone(self.sub.last_event_at)
        self.assertFalse(Invoices.exists())
        self.assertFalse(Payments.exists())

    def test_explicit_dry_run_flag_means_the_same(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription(status="canceled")])

        reconcile(fake, "--dry-run")

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)

    def test_dry_run_and_apply_cannot_be_combined(self) -> None:
        with self.assertRaises(CommandError):
            reconcile(FakeStripe(), "--dry-run", "--apply")

    def test_dry_run_leaves_one_audit_event_with_the_findings(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription(status="canceled")])
        before = Audits.count()

        reconcile(fake)

        self.assertEqual(Audits.count(), before + 1)
        event = audit_events(BILLING_RECONCILE_RUN)[0]
        payload = event.extra["payload"]
        self.assertIs(payload["dry_run"], True)
        self.assertEqual(payload["mismatch_count"], 1)
        self.assertEqual(payload["repaired"], 0)
        finding = payload["mismatches"][0]
        self.assertEqual(finding["kind"], "subscription_state")
        self.assertEqual(
            finding["detail"]["status"], {"local": "active", "stripe": "canceled"}
        )
        self.assertEqual(event.correlation_id, payload["run_id"])

    def test_matching_state_is_a_clean_run(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription()])

        output = reconcile(fake, "--apply")

        self.assertIn("Checked 1 subscriptions: 0 mismatches", output)
        self.assertEqual(audit_events(BILLING_RECONCILE_REPAIR), [])

    def test_json_report_is_parseable(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription(status="past_due")])

        report = json.loads(reconcile(fake, "--json"))

        self.assertIs(report["dry_run"], True)
        self.assertEqual(report["mismatches"][0]["stripe_id"], "sub_rec")

    def test_days_sets_the_invoice_window(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription()])

        reconcile(fake, "--days", "7")

        expected = timezone.now() - timedelta(days=7)
        self.assertLess(abs(fake.invoice_since - expected), timedelta(minutes=1))

    def test_days_has_to_be_positive(self) -> None:
        with self.assertRaises(CommandError):
            reconcile(FakeStripe(), "--days", "0")


@override_settings(TESTING=True, DISABLE_RATE_LIMITING=True)
class SubscriptionRepairTests(ReconcileTestCase):
    def test_apply_repairs_the_row_and_audits_before_and_after(self) -> None:
        fake = FakeStripe(
            subscriptions=[
                remote_subscription(status="canceled", current_period_end=1_800_000_000)
            ]
        )

        output = reconcile(fake, "--apply")

        self.assertIn("1 repaired", output)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)
        self.assertEqual(self.sub.status, "canceled")
        self.assertEqual(
            self.sub.current_period_end,
            datetime.fromtimestamp(1_800_000_000, tz=dt_timezone.utc),
        )

        event = audit_events(BILLING_RECONCILE_REPAIR)[0]
        self.assertEqual(event.resource_type, "billing.customersubscription")
        self.assertEqual(event.resource_id, str(self.sub.pk))
        self.assertEqual(event.action, AuditEvent.ACTION_UPDATED)
        detail = event.extra["payload"]["detail"]
        self.assertEqual(detail["active"], {"local": True, "stripe": False})

        run = audit_events(BILLING_RECONCILE_RUN)[0]
        self.assertIs(run.extra["payload"]["dry_run"], False)
        self.assertEqual(run.extra["payload"]["repaired"], 1)
        self.assertEqual(run.correlation_id, event.correlation_id)

    def test_second_apply_finds_nothing(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription(status="canceled")])

        reconcile(fake, "--apply")
        output = reconcile(fake, "--apply")

        self.assertIn("0 mismatches", output)

    def test_delayed_event_cannot_undo_a_repair(self) -> None:
        reconcile(
            FakeStripe(subscriptions=[remote_subscription(status="canceled")]),
            "--apply",
        )
        older = int((timezone.now() - timedelta(minutes=5)).timestamp())

        client: Any = APIClient()
        response = client.post(
            "/api/billing/webhook/",
            data=json.dumps(
                {
                    "id": "evt_after_repair",
                    "type": "customer.subscription.updated",
                    "created": older,
                    "data": {"object": remote_subscription(status="active")},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)
        self.assertEqual(Events.get().outcome, StripeEvent.OUTCOME_STALE)

    def test_repair_backs_off_when_a_newer_event_landed_during_the_run(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription(status="canceled")])
        real_lookup = fake.subscription

        def newer_event_lands(subscription_id: str) -> Any:
            Subscriptions.filter(pk=self.sub.pk).update(
                last_event_at=timezone.now() + timedelta(minutes=1)
            )
            return real_lookup(subscription_id)

        with patch.object(fake, "subscription", newer_event_lands):
            output = reconcile(fake, "--apply")

        self.assertIn("a newer event landed", output)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(audit_events(BILLING_RECONCILE_REPAIR), [])

    def test_missed_checkout_links_the_live_subscription(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(
            stripe_subscription_id=None, active=False, status="inactive"
        )
        fake = FakeStripe(
            subscriptions=[
                remote_subscription("sub_old", status="canceled", created=1),
                remote_subscription(
                    "sub_live",
                    created=2,
                    items={"data": [{"price": {"id": "price_pro"}}]},
                ),
            ]
        )

        reconcile(fake, "--apply")

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.stripe_subscription_id, "sub_live")
        self.assertTrue(self.sub.active)
        self.assertEqual(self.sub.plan, self.pro)

    def test_live_subscription_replaces_a_canceled_bound_one(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(active=False, status="canceled")
        fake = FakeStripe(
            subscriptions=[
                remote_subscription(status="canceled"),
                remote_subscription("sub_new"),
            ]
        )

        reconcile(fake, "--apply")

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.stripe_subscription_id, "sub_new")
        self.assertTrue(self.sub.active)

    def test_active_on_stripe_clears_a_stale_payment_failure(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(payment_failed_at=timezone.now())

        reconcile(FakeStripe(subscriptions=[remote_subscription()]), "--apply")

        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.payment_failed_at)

    def test_subscription_missing_on_stripe_is_never_auto_repaired(self) -> None:
        output = reconcile(FakeStripe(), "--apply")

        self.assertIn("subscription_missing", output)
        self.assertIn("1 need a manual look", output)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(audit_events(BILLING_RECONCILE_REPAIR), [])

    def test_row_without_any_subscription_is_not_a_mismatch(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(
            stripe_subscription_id=None, active=False, status="inactive"
        )

        output = reconcile(FakeStripe(), "--apply")

        self.assertIn("0 mismatches", output)

    def test_failed_audit_write_rolls_the_repair_back(self) -> None:
        fake = FakeStripe(subscriptions=[remote_subscription(status="canceled")])

        with patch("apps.billing.reconciliation.record_admin_event", return_value=None):
            with self.assertRaises(CommandError):
                reconcile(fake, "--apply")

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertIsNone(self.sub.last_event_at)

    def test_customer_option_limits_the_run(self) -> None:
        other: Any = get_user_model()._default_manager.create_user(
            username="reconcile-other",
            email="other@example.com",
            password="test-password",
        )
        Subscriptions.create(
            user=other,
            stripe_customer_id="cus_other",
            stripe_subscription_id="sub_other",
            active=True,
            status="active",
        )
        fake = FakeStripe(
            subscriptions=[
                remote_subscription(status="canceled"),
                remote_subscription(
                    "sub_other", status="canceled", customer="cus_other"
                ),
            ]
        )

        reconcile(fake, "--apply", "--customer", "cus_other")

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertFalse(Subscriptions.get(stripe_customer_id="cus_other").active)

    def test_rows_from_mock_checkouts_are_skipped(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(stripe_customer_id="cus_mock_7")

        output = reconcile(FakeStripe(), "--apply")

        self.assertIn("Checked 0 subscriptions", output)

    def test_one_failing_customer_does_not_stop_the_others(self) -> None:
        other: Any = get_user_model()._default_manager.create_user(
            username="reconcile-other",
            email="other@example.com",
            password="test-password",
        )
        Subscriptions.create(
            user=other,
            stripe_customer_id="cus_other",
            stripe_subscription_id="sub_other",
            active=True,
            status="active",
        )
        fake = FakeStripe(
            subscriptions=[
                remote_subscription(),
                remote_subscription(
                    "sub_other", status="canceled", customer="cus_other"
                ),
            ],
            failing_customers=["cus_rec"],
        )
        out = StringIO()

        with patch(BUILD_CLIENT, return_value=fake):
            with self.assertRaises(CommandError):
                call_command("reconcile_billing", "--apply", stdout=out)

        self.assertIn("error cus_rec", out.getvalue())
        self.assertFalse(Subscriptions.get(stripe_customer_id="cus_other").active)
        run = audit_events(BILLING_RECONCILE_RUN)[0]
        self.assertEqual(len(run.extra["payload"]["errors"]), 1)


class InvoiceRepairTests(ReconcileTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.subscriptions = [remote_subscription()]

    @patch("apps.billing.webhooks.async_task")
    def test_paid_invoice_missing_locally_is_created(self, mock_task: Any) -> None:
        fake = FakeStripe(self.subscriptions, invoices=[remote_invoice()])

        reconcile(fake, "--apply")

        invoice = Invoices.get(stripe_invoice_id="in_rec")
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(str(invoice.amount), "20.00")
        self.assertEqual(Payments.get(stripe_charge_id="ch_in_rec").user, self.user)
        mock_task.assert_called_once_with(
            "apps.billing.tasks.generate_invoice_pdf_task", invoice.pk
        )
        event = audit_events(BILLING_RECONCILE_REPAIR)[0]
        self.assertEqual(event.resource_type, "billing.invoice")
        self.assertEqual(event.action, AuditEvent.ACTION_CREATED)

    @patch("apps.billing.webhooks.async_task")
    def test_repeat_run_does_not_duplicate_the_invoice(self, mock_task: Any) -> None:
        fake = FakeStripe(self.subscriptions, invoices=[remote_invoice()])

        reconcile(fake, "--apply")
        output = reconcile(fake, "--apply")

        self.assertIn("0 mismatches", output)
        self.assertEqual(Invoices.count(), 1)
        self.assertEqual(Payments.count(), 1)

    @patch("apps.billing.webhooks.async_task")
    def test_open_invoice_paid_on_stripe_is_settled(self, mock_task: Any) -> None:
        Invoices.create(
            user=self.user, stripe_invoice_id="in_rec", amount=20, status="open"
        )
        fake = FakeStripe(self.subscriptions, invoices=[remote_invoice()])

        reconcile(fake, "--apply")

        self.assertEqual(Invoices.get(stripe_invoice_id="in_rec").status, "paid")
        self.assertEqual(Payments.get(stripe_charge_id="ch_in_rec").status, "succeeded")

    def test_voided_invoice_updates_the_local_status(self) -> None:
        Invoices.create(
            user=self.user, stripe_invoice_id="in_rec", amount=20, status="open"
        )
        fake = FakeStripe(self.subscriptions, invoices=[remote_invoice(status="void")])

        reconcile(fake, "--apply")

        self.assertEqual(Invoices.get(stripe_invoice_id="in_rec").status, "void")
        self.assertFalse(Payments.exists())

    def test_unpaid_invoice_with_no_local_row_is_not_a_mismatch(self) -> None:
        fake = FakeStripe(self.subscriptions, invoices=[remote_invoice(status="open")])

        output = reconcile(fake, "--apply")

        self.assertIn("0 mismatches", output)
        self.assertFalse(Invoices.exists())

    def test_invoice_for_a_row_without_a_user_needs_a_manual_look(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(user=None)
        fake = FakeStripe(self.subscriptions, invoices=[remote_invoice()])

        output = reconcile(fake, "--apply")

        self.assertIn("needs a manual look", output)
        self.assertFalse(Invoices.exists())


class UnmatchedEventTests(ReconcileTestCase):
    def ledger_row(self, customer_id: str, age_days: int = 1) -> None:
        Events.create(
            event_id=f"evt_{customer_id}_{age_days}",
            event_type="customer.subscription.updated",
            customer_id=customer_id,
            event_created_at=timezone.now() - timedelta(days=age_days),
            outcome=StripeEvent.OUTCOME_UNMATCHED,
        )

    def test_events_for_an_unknown_customer_are_reported(self) -> None:
        self.ledger_row("cus_nobody")
        fake = FakeStripe(subscriptions=[remote_subscription()])

        output = reconcile(fake, "--apply")

        self.assertIn("event_unmatched", output)
        self.assertIn("evt_cus_nobody_1", output)
        self.assertIn("1 need a manual look", output)

    def test_events_for_a_customer_we_know_are_not_reported(self) -> None:
        self.ledger_row("cus_rec")

        output = reconcile(FakeStripe(subscriptions=[remote_subscription()]))

        self.assertNotIn("event_unmatched", output)

    def test_events_outside_the_window_are_not_reported(self) -> None:
        self.ledger_row("cus_nobody", age_days=40)

        output = reconcile(FakeStripe(subscriptions=[remote_subscription()]))

        self.assertNotIn("event_unmatched", output)


class StripeClientTests(TestCase):
    """The thin layer the fake replaces, with real Stripe objects and no network."""

    def test_subscription_comes_back_as_a_plain_dict(self) -> None:
        found = stripe.Subscription.construct_from(
            {"id": "sub_1", "object": "subscription", "status": "active"}, "sk_test"
        )

        with patch.object(stripe.Subscription, "retrieve", return_value=found):
            result = StripeClient().subscription("sub_1")

        self.assertIsInstance(result, dict)
        self.assertEqual(result, found.to_dict())

    def test_missing_subscription_is_none(self) -> None:
        error = stripe.InvalidRequestError(
            "No such subscription", "id", code="resource_missing"
        )

        with patch.object(stripe.Subscription, "retrieve", side_effect=error):
            self.assertIsNone(StripeClient().subscription("sub_gone"))

    def test_other_stripe_errors_are_raised(self) -> None:
        error = stripe.InvalidRequestError(
            "Bad request", "id", code="parameter_invalid"
        )

        with patch.object(stripe.Subscription, "retrieve", side_effect=error):
            with self.assertRaises(stripe.InvalidRequestError):
                StripeClient().subscription("sub_bad")

    def test_lists_are_flattened_to_plain_dicts(self) -> None:
        listing = stripe.ListObject.construct_from(
            {
                "object": "list",
                "has_more": False,
                "data": [{"id": "in_1", "object": "invoice", "status": "paid"}],
            },
            "sk_test",
        )

        with patch.object(stripe.Invoice, "list", return_value=listing) as mock_list:
            result = StripeClient().invoices("cus_1", timezone.now())

        self.assertEqual(result[0]["id"], "in_1")
        self.assertIsInstance(result[0], dict)
        self.assertEqual(mock_list.call_args.kwargs["customer"], "cus_1")


class BuildClientTests(TestCase):
    def test_refuses_while_testing_so_a_test_cannot_reach_stripe(self) -> None:
        with patch.object(stripe, "api_key", "sk_live_looks_real"):
            with patch.object(stripe.Subscription, "retrieve") as mock_retrieve:
                with self.assertRaises(CommandError):
                    call_command("reconcile_billing", stdout=StringIO())

        mock_retrieve.assert_not_called()

    @override_settings(TESTING=False)
    def test_refuses_in_mock_mode(self) -> None:
        for key in (None, "", "sk_test_mock"):
            with patch.object(stripe, "api_key", key):
                with self.assertRaises(CommandError):
                    build_client()

    @override_settings(TESTING=False)
    def test_real_key_gives_the_stripe_client(self) -> None:
        with patch.object(stripe, "api_key", "sk_test_not_a_mock"):
            self.assertIsInstance(build_client(), StripeClient)
