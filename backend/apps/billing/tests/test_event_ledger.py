import json
import time
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.billing.models import (
    CustomerSubscription,
    Invoice,
    Payment,
    StripeEvent,
    SubscriptionPlan,
)

EventModel: Any = StripeEvent
Subscriptions: Any = CustomerSubscription._default_manager
Events: Any = StripeEvent._default_manager
Invoices: Any = Invoice._default_manager
Payments: Any = Payment._default_manager

T1 = 1_800_000_100
T2 = 1_800_000_200
T3 = 1_800_000_300


def at(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)


def subscription_object(status: str = "active", **extra: Any) -> dict:
    return {
        "id": "sub_ledger",
        "customer": "cus_ledger",
        "status": status,
        **extra,
    }


class LedgerTestCase(TestCase):
    def setUp(self) -> None:
        self.client: Any = APIClient()
        self.client.raise_request_exception = False
        self.user: Any = get_user_model()._default_manager.create_user(
            username="ledger-user",
            email="ledger@example.com",
            password="test-password",
        )
        self.pro: Any = SubscriptionPlan._default_manager.create(
            name="Pro", stripe_price_id="price_pro", price=20
        )
        self.team: Any = SubscriptionPlan._default_manager.create(
            name="Team", stripe_price_id="price_team", price=50
        )
        self.sub: Any = Subscriptions.create(
            user=self.user,
            stripe_customer_id="cus_ledger",
            stripe_subscription_id="sub_ledger",
            plan=self.pro,
            active=True,
            status="active",
        )

    def post(
        self, event_type: str, event_object: dict, created: int, event_id: str = ""
    ) -> Any:
        return self.client.post(
            "/api/billing/webhook/",
            data=json.dumps(
                {
                    "id": event_id or f"evt_{event_type}_{created}",
                    "type": event_type,
                    "created": created,
                    "data": {"object": event_object},
                }
            ),
            content_type="application/json",
        )

    def post_checkout(self, created: int, subscription: str = "sub_ledger") -> Any:
        return self.post(
            "checkout.session.completed",
            {
                "id": f"cs_{created}",
                "customer": "cus_ledger",
                "subscription": subscription,
                "metadata": {"user_id": self.user.id, "plan_id": self.pro.id},
            },
            created,
        )

    def outcome(self, event_id: str) -> str:
        return Events.get(event_id=event_id).outcome


@override_settings(TESTING=True, DISABLE_RATE_LIMITING=True)
class DuplicateEventTests(LedgerTestCase):
    def test_duplicate_subscription_update_does_not_reapply(self) -> None:
        event = subscription_object("past_due")
        self.post("customer.subscription.updated", event, T1, "evt_dup")
        Subscriptions.filter(pk=self.sub.pk).update(status="active", active=True)

        response = self.post("customer.subscription.updated", event, T1, "evt_dup")

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(Events.filter(event_id="evt_dup").count(), 1)

    def test_duplicate_checkout_does_not_turn_access_back_on(self) -> None:
        self.post_checkout(T1)
        Subscriptions.filter(pk=self.sub.pk).update(status="canceled", active=False)

        response = self.post_checkout(T1)

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)

    def test_duplicate_delete_does_not_cancel_a_later_state(self) -> None:
        event = subscription_object("canceled")
        self.post("customer.subscription.deleted", event, T1, "evt_del")
        Subscriptions.filter(pk=self.sub.pk).update(status="active", active=True)

        self.post("customer.subscription.deleted", event, T1, "evt_del")

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)

    @patch("apps.billing.webhooks.async_task")
    def test_duplicate_invoice_paid_writes_and_queues_once(
        self, mock_task: Any
    ) -> None:
        invoice = {
            "id": "in_dup",
            "customer": "cus_ledger",
            "amount_paid": 2000,
            "currency": "usd",
            "charge": "ch_dup",
        }
        self.post("invoice.paid", invoice, T1, "evt_paid")
        self.post("invoice.paid", invoice, T1, "evt_paid")

        self.assertEqual(Invoices.filter(stripe_invoice_id="in_dup").count(), 1)
        self.assertEqual(Payments.filter(stripe_charge_id="ch_dup").count(), 1)
        mock_task.assert_called_once()

    @patch("apps.billing.webhooks.async_task")
    def test_same_invoice_under_two_event_ids_stays_idempotent(
        self, mock_task: Any
    ) -> None:
        invoice = {
            "id": "in_twice",
            "customer": "cus_ledger",
            "amount_paid": 2000,
            "charge": "ch_twice",
        }
        self.post("invoice.paid", invoice, T1, "evt_a")
        self.post("invoice.paid", invoice, T2, "evt_b")

        self.assertEqual(Invoices.filter(stripe_invoice_id="in_twice").count(), 1)
        self.assertEqual(Payments.filter(stripe_charge_id="ch_twice").count(), 1)
        mock_task.assert_called_once()

    def test_losing_a_race_on_the_unique_id_applies_nothing(self) -> None:
        # What a second worker sees: its first read misses the row, then its insert
        # hits the unique constraint because the first worker committed in between.
        Events.create(
            event_id="evt_race",
            event_type="customer.subscription.updated",
            event_created_at=at(T1),
            outcome=StripeEvent.OUTCOME_APPLIED,
        )
        real_get = QuerySet.get
        calls = []

        def miss_first_read(queryset: Any, *args: Any, **kwargs: Any) -> Any:
            if queryset.model is StripeEvent and not calls:
                calls.append(kwargs)
                raise EventModel.DoesNotExist
            return real_get(queryset, *args, **kwargs)

        with patch.object(QuerySet, "get", miss_first_read):
            response = self.post(
                "customer.subscription.updated",
                subscription_object("past_due"),
                T1,
                "evt_race",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(calls), 1)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")

    def test_unhandled_type_is_recorded_as_ignored(self) -> None:
        response = self.post(
            "customer.created", {"id": "cus_new"}, T1, "evt_customer_created"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.outcome("evt_customer_created"), StripeEvent.OUTCOME_IGNORED
        )

    def test_mock_events_without_an_id_are_not_treated_as_one_delivery(self) -> None:
        for status in ("past_due", "active"):
            self.client.post(
                "/api/billing/webhook/",
                data=json.dumps(
                    {
                        "type": "customer.subscription.updated",
                        "data": {"object": subscription_object(status)},
                    }
                ),
                content_type="application/json",
            )

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(Events.count(), 2)


@override_settings(TESTING=True, DISABLE_RATE_LIMITING=True)
class EventOrderingTests(LedgerTestCase):
    def test_delayed_update_cannot_revive_a_canceled_subscription(self) -> None:
        self.post(
            "customer.subscription.deleted",
            subscription_object("canceled"),
            T2,
            "evt_deleted",
        )

        response = self.post(
            "customer.subscription.updated",
            subscription_object("active"),
            T1,
            "evt_late",
        )

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)
        self.assertEqual(self.sub.status, "canceled")
        self.assertEqual(self.sub.last_event_at, at(T2))
        self.assertEqual(self.outcome("evt_late"), StripeEvent.OUTCOME_STALE)

    def test_cancellation_wins_a_same_second_tie(self) -> None:
        self.post(
            "customer.subscription.deleted",
            subscription_object("canceled"),
            T2,
            "evt_a",
        )
        self.post(
            "customer.subscription.updated", subscription_object("active"), T2, "evt_b"
        )

        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)
        self.assertEqual(self.outcome("evt_b"), StripeEvent.OUTCOME_STALE)

    def test_same_second_updates_both_apply(self) -> None:
        self.post(
            "customer.subscription.updated",
            subscription_object("past_due"),
            T2,
            "evt_a",
        )
        self.post(
            "customer.subscription.updated", subscription_object("active"), T2, "evt_b"
        )

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")

    def test_late_cancel_still_applies_after_a_newer_invoice_failure(self) -> None:
        self.post(
            "invoice.payment_failed",
            {"id": "in_final", "customer": "cus_ledger", "amount_due": 2000},
            T2,
            "evt_failed",
        )

        self.post(
            "customer.subscription.deleted",
            subscription_object("canceled"),
            T1,
            "evt_deleted",
        )

        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)
        self.assertEqual(self.sub.status, "canceled")
        self.assertEqual(self.sub.last_event_at, at(T2))
        self.assertEqual(self.outcome("evt_deleted"), StripeEvent.OUTCOME_APPLIED)

    def test_older_update_does_not_overwrite_a_newer_one(self) -> None:
        self.post(
            "customer.subscription.updated",
            subscription_object(
                "active",
                current_period_end=T3,
                items={"data": [{"price": {"id": "price_team"}}]},
            ),
            T2,
            "evt_new",
        )

        self.post(
            "customer.subscription.updated",
            subscription_object(
                "past_due",
                current_period_end=T1,
                items={"data": [{"price": {"id": "price_pro"}}]},
            ),
            T1,
            "evt_old",
        )

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(self.sub.plan, self.team)
        self.assertEqual(self.sub.current_period_end, at(T3))
        self.assertEqual(self.outcome("evt_old"), StripeEvent.OUTCOME_STALE)

    def test_updates_in_order_all_apply(self) -> None:
        self.post(
            "customer.subscription.updated",
            subscription_object("past_due"),
            T1,
            "evt_a",
        )
        self.post(
            "customer.subscription.updated", subscription_object("active"), T2, "evt_b"
        )

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(self.sub.last_event_at, at(T2))
        self.assertEqual(self.outcome("evt_a"), StripeEvent.OUTCOME_APPLIED)

    def test_period_end_is_read_from_items_on_newer_api_versions(self) -> None:
        self.post(
            "customer.subscription.updated",
            subscription_object("active", items={"data": [{"current_period_end": T3}]}),
            T1,
        )

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, at(T3))

    def test_late_payment_failure_is_recorded_without_touching_state(self) -> None:
        self.post(
            "customer.subscription.updated", subscription_object("active"), T2, "evt_ok"
        )

        self.post(
            "invoice.payment_failed",
            {"id": "in_late", "customer": "cus_ledger", "amount_due": 2000},
            T1,
            "evt_failed",
        )

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertIsNone(self.sub.payment_failed_at)
        self.assertEqual(Invoices.get(stripe_invoice_id="in_late").status, "open")
        self.assertEqual(
            Payments.get(stripe_charge_id="ch_failed_in_late").status, "failed"
        )
        self.assertEqual(self.outcome("evt_failed"), StripeEvent.OUTCOME_STALE)

    @patch("apps.billing.webhooks.async_task")
    def test_paid_after_a_failed_attempt_settles_the_invoice(
        self, mock_task: Any
    ) -> None:
        self.post(
            "invoice.payment_failed",
            {"id": "in_retry", "customer": "cus_ledger", "amount_due": 2000},
            T1,
        )
        mock_task.assert_not_called()

        self.post(
            "invoice.paid",
            {
                "id": "in_retry",
                "customer": "cus_ledger",
                "amount_paid": 2000,
                "charge": "ch_retry",
            },
            T2,
        )

        self.assertEqual(Invoices.get(stripe_invoice_id="in_retry").status, "paid")
        self.assertEqual(Payments.get(stripe_charge_id="ch_retry").status, "succeeded")
        mock_task.assert_called_once()

    @patch("apps.billing.webhooks.async_task")
    def test_late_failure_does_not_reopen_a_paid_invoice(self, mock_task: Any) -> None:
        self.post(
            "invoice.paid",
            {
                "id": "in_flip",
                "customer": "cus_ledger",
                "amount_paid": 2000,
                "charge": "ch_flip",
            },
            T2,
        )

        self.post(
            "invoice.payment_failed",
            {"id": "in_flip", "customer": "cus_ledger", "amount_due": 2000},
            T1,
        )

        self.assertEqual(Invoices.get(stripe_invoice_id="in_flip").status, "paid")

    def test_delayed_checkout_links_the_row_but_keeps_newer_state(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(
            stripe_subscription_id=None, plan=None
        )
        self.post(
            "customer.subscription.updated",
            subscription_object("past_due"),
            T2,
            "evt_up",
        )

        self.post_checkout(T1)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.stripe_subscription_id, "sub_ledger")
        self.assertEqual(self.sub.plan, self.pro)
        self.assertEqual(self.sub.status, "past_due")
        self.assertFalse(self.sub.active)
        self.assertEqual(self.sub.last_event_at, at(T2))
        self.assertEqual(self.outcome(f"evt_checkout.session.completed_{T1}"), "stale")

    def test_delayed_checkout_does_not_replace_a_newer_plan(self) -> None:
        self.post(
            "customer.subscription.updated",
            subscription_object(
                "active", items={"data": [{"price": {"id": "price_team"}}]}
            ),
            T2,
        )

        self.post_checkout(T1)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, self.team)

    def test_delayed_checkout_cannot_revive_a_canceled_subscription(self) -> None:
        self.post("customer.subscription.deleted", subscription_object("canceled"), T2)

        self.post_checkout(T1)

        self.sub.refresh_from_db()
        self.assertFalse(self.sub.active)
        self.assertEqual(self.sub.status, "canceled")

    def test_delete_before_checkout_cancels_the_unlinked_row(self) -> None:
        Subscriptions.filter(pk=self.sub.pk).update(stripe_subscription_id=None)
        self.post("customer.subscription.deleted", subscription_object("canceled"), T2)

        self.post_checkout(T1)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.stripe_subscription_id, "sub_ledger")
        self.assertFalse(self.sub.active)

    def test_new_purchase_after_a_cancel_is_not_lost_to_the_clock(self) -> None:
        self.post("customer.subscription.deleted", subscription_object("canceled"), T2)

        self.post_checkout(T1, subscription="sub_replacement")

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(self.sub.stripe_subscription_id, "sub_replacement")
        self.assertEqual(self.sub.last_event_at, at(T1))

    def test_late_checkout_for_a_replaced_subscription_changes_nothing(self) -> None:
        self.post(
            "customer.subscription.updated", subscription_object("active"), T2, "evt_up"
        )

        self.post_checkout(T1, subscription="sub_older")

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.stripe_subscription_id, "sub_ledger")
        self.assertEqual(self.sub.last_event_at, at(T2))

    def test_event_for_another_subscription_leaves_a_live_row_alone(self) -> None:
        self.post(
            "customer.subscription.updated",
            {"id": "sub_other", "customer": "cus_ledger", "status": "canceled"},
            T2,
            "evt_other",
        )

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(self.sub.stripe_subscription_id, "sub_ledger")
        self.assertEqual(self.outcome("evt_other"), StripeEvent.OUTCOME_UNMATCHED)

    def test_update_for_a_new_subscription_moves_a_canceled_row_over(self) -> None:
        self.post("customer.subscription.deleted", subscription_object("canceled"), T1)

        self.post(
            "customer.subscription.updated",
            {"id": "sub_next", "customer": "cus_ledger", "status": "active"},
            T2,
        )

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(self.sub.stripe_subscription_id, "sub_next")

    def test_late_delete_of_a_replaced_subscription_is_harmless(self) -> None:
        self.post_checkout(T2, subscription="sub_replacement")
        self.post(
            "customer.subscription.deleted",
            subscription_object("canceled"),
            T3,
            "evt_del",
        )

        self.sub.refresh_from_db()
        self.assertTrue(self.sub.active)
        self.assertEqual(self.outcome("evt_del"), StripeEvent.OUTCOME_UNMATCHED)

    def test_event_for_an_unknown_customer_is_recorded_as_unmatched(self) -> None:
        response = self.post(
            "customer.subscription.updated",
            {"id": "sub_nobody", "customer": "cus_nobody", "status": "active"},
            T1,
            "evt_nobody",
        )

        self.assertEqual(response.status_code, 200)
        event = Events.get(event_id="evt_nobody")
        self.assertEqual(event.outcome, StripeEvent.OUTCOME_UNMATCHED)
        self.assertEqual(event.customer_id, "cus_nobody")
        self.assertEqual(event.object_id, "sub_nobody")


@override_settings(TESTING=True, DISABLE_RATE_LIMITING=True)
class PartiallyProcessedEventTests(LedgerTestCase):
    invoice = {
        "id": "in_crash",
        "customer": "cus_ledger",
        "amount_paid": 2000,
        "charge": "ch_crash",
    }

    @patch("apps.billing.webhooks.async_task")
    def test_crash_after_the_invoice_write_keeps_nothing_and_retry_works(
        self, mock_task: Any
    ) -> None:
        with patch.object(
            Payment._default_manager,
            "get_or_create",
            side_effect=RuntimeError("database went away"),
        ) as payment_write:
            failed = self.post("invoice.paid", self.invoice, T1, "evt_crash")

        payment_write.assert_called_once()
        self.assertEqual(failed.status_code, 500)
        self.assertFalse(Events.filter(event_id="evt_crash").exists())
        self.assertFalse(Invoices.filter(stripe_invoice_id="in_crash").exists())
        mock_task.assert_not_called()

        retried = self.post("invoice.paid", self.invoice, T1, "evt_crash")

        self.assertEqual(retried.status_code, 200)
        self.assertEqual(self.outcome("evt_crash"), StripeEvent.OUTCOME_APPLIED)
        self.assertEqual(Invoices.filter(stripe_invoice_id="in_crash").count(), 1)
        self.assertEqual(Payments.filter(stripe_charge_id="ch_crash").count(), 1)
        mock_task.assert_called_once()

    def test_failed_payment_rolls_the_subscription_back_too(self) -> None:
        event = {"id": "in_crash", "customer": "cus_ledger", "amount_due": 2000}
        with patch.object(
            Payment._default_manager,
            "get_or_create",
            side_effect=RuntimeError("database went away"),
        ) as payment_write:
            failed = self.post("invoice.payment_failed", event, T1, "evt_crash")

        payment_write.assert_called_once()
        self.assertEqual(failed.status_code, 500)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertIsNone(self.sub.last_event_at)
        self.assertFalse(Events.filter(event_id="evt_crash").exists())

        retried = self.post("invoice.payment_failed", event, T1, "evt_crash")

        self.assertEqual(retried.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "past_due")

    def test_crash_while_finishing_the_ledger_row_rolls_the_mutation_back(self) -> None:
        real_save = StripeEvent.save
        calls = []

        def fail_on_outcome(event: Any, *args: Any, **kwargs: Any) -> Any:
            if "update_fields" not in kwargs:
                return real_save(event, *args, **kwargs)
            calls.append(Subscriptions.get(pk=self.sub.pk).status)
            raise RuntimeError("database went away")

        with patch.object(StripeEvent, "save", fail_on_outcome):
            failed = self.post(
                "customer.subscription.updated",
                subscription_object("past_due"),
                T1,
                "evt_crash",
            )

        self.assertEqual(calls, ["past_due"])
        self.assertEqual(failed.status_code, 500)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertFalse(Events.filter(event_id="evt_crash").exists())

    @patch(
        "apps.billing.webhooks.async_task", side_effect=RuntimeError("broker is down")
    )
    def test_failing_to_queue_the_pdf_does_not_undo_the_payment(
        self, mock_task: Any
    ) -> None:
        response = self.post("invoice.paid", self.invoice, T1, "evt_broker")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.outcome("evt_broker"), StripeEvent.OUTCOME_APPLIED)
        self.assertEqual(Invoices.filter(stripe_invoice_id="in_crash").count(), 1)


SECRET = "whsec_ledger_test"


@override_settings(
    TESTING=False, STRIPE_WEBHOOK_SECRET=SECRET, DISABLE_RATE_LIMITING=True
)
class SignedDeliveryTests(LedgerTestCase):
    """The non-mock path: real signature check and real Stripe objects."""

    def setUp(self) -> None:
        super().setUp()
        api_key = patch.object(stripe, "api_key", "sk_test_not_a_mock")
        api_key.start()
        self.addCleanup(api_key.stop)

    def payload(self, event_id: str, created: int, status: str = "past_due") -> str:
        return json.dumps(
            {
                "id": event_id,
                "object": "event",
                "type": "customer.subscription.updated",
                "created": created,
                "data": {
                    "object": {
                        "object": "subscription",
                        **subscription_object(status),
                        "items": {
                            "object": "list",
                            "data": [
                                {
                                    "object": "subscription_item",
                                    "current_period_end": T3,
                                    "price": {"object": "price", "id": "price_team"},
                                }
                            ],
                        },
                    }
                },
            }
        )

    def deliver(
        self, payload: str, *, signed_at: Any = None, secret: str = SECRET
    ) -> Any:
        header = stripe.WebhookSignature.generate_signature_header(
            payload, secret, timestamp=signed_at or int(time.time())
        )
        return self.client.post(
            "/api/billing/webhook/",
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=header,
        )

    def test_real_stripe_objects_are_applied(self) -> None:
        response = self.deliver(self.payload("evt_signed", int(time.time())))

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "past_due")
        self.assertEqual(self.sub.plan, self.team)
        self.assertEqual(self.sub.current_period_end, at(T3))
        self.assertEqual(self.outcome("evt_signed"), StripeEvent.OUTCOME_APPLIED)

    def test_missing_signature_is_rejected(self) -> None:
        response = self.client.post(
            "/api/billing/webhook/",
            data=self.payload("evt_unsigned", int(time.time())),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Events.exists())

    def test_wrong_secret_is_rejected_and_records_nothing(self) -> None:
        response = self.deliver(
            self.payload("evt_forged", int(time.time())), secret="whsec_wrong"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Events.exists())
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")

    def test_old_signature_timestamp_is_rejected(self) -> None:
        response = self.deliver(
            self.payload("evt_replayed", int(time.time())),
            signed_at=int(time.time()) - 301,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Events.exists())

    def test_old_event_with_a_fresh_signature_is_still_accepted(self) -> None:
        # Stripe signs each retry again, so an event from three days ago arrives
        # with a current t=. Only the signature age may be limited, not the event's.
        three_days_ago = int(time.time()) - 3 * 24 * 60 * 60

        response = self.deliver(self.payload("evt_retry", three_days_ago))

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "past_due")
        self.assertEqual(self.sub.last_event_at, at(three_days_ago))

    def test_replaying_a_signed_request_applies_it_once(self) -> None:
        payload = self.payload("evt_twice", int(time.time()))
        self.deliver(payload)
        Subscriptions.filter(pk=self.sub.pk).update(status="active")

        response = self.deliver(payload)

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(Events.filter(event_id="evt_twice").count(), 1)

    def test_checkout_reads_the_period_end_from_stripe(self) -> None:
        payload = json.dumps(
            {
                "id": "evt_checkout",
                "object": "event",
                "type": "checkout.session.completed",
                "created": int(time.time()),
                "data": {
                    "object": {
                        "object": "checkout.session",
                        "id": "cs_signed",
                        "customer": "cus_ledger",
                        "subscription": "sub_ledger",
                        "metadata": {
                            "user_id": str(self.user.id),
                            "plan_id": str(self.pro.id),
                        },
                    }
                },
            }
        )
        fetched = stripe.Subscription.construct_from(
            {
                "id": "sub_ledger",
                "object": "subscription",
                "items": {
                    "object": "list",
                    "data": [{"object": "subscription_item", "current_period_end": T3}],
                },
            },
            "sk_test_not_a_mock",
        )

        with patch.object(stripe.Subscription, "retrieve", return_value=fetched):
            response = self.deliver(payload)

        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, at(T3))
