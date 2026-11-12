import datetime
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from apps.webhooks.models import InboundWebhookEvent
from apps.webhooks.services.inbound_processor import process_inbound_webhook


class InboundWebhookProtectionTests(TestCase):
    def setUp(self):
        InboundWebhookEvent.objects.all().delete()

    def test_duplicate_events_acknowledged_without_repeating_side_effects(self):
        counter = {"called": 0}

        def side_effect(payload):
            counter["called"] += 1

        payload = {"action": "push", "ref": "refs/heads/main"}
        event_id = "gh-delivery-uuid-1"

        # First delivery
        ack1, outcome1, record1 = process_inbound_webhook(
            provider="github",
            event_id=event_id,
            event_type="push",
            payload=payload,
            signature_valid=True,
            handler=side_effect,
        )
        self.assertTrue(ack1)
        self.assertEqual(outcome1, "processed")
        self.assertEqual(counter["called"], 1)
        self.assertEqual(InboundWebhookEvent.objects.count(), 1)

        # Duplicate delivery retry from provider
        ack2, outcome2, record2 = process_inbound_webhook(
            provider="github",
            event_id=event_id,
            event_type="push",
            payload=payload,
            signature_valid=True,
            handler=side_effect,
        )
        self.assertTrue(ack2)
        self.assertEqual(outcome2, "duplicate_acknowledged")
        # Side effect was NOT repeated
        self.assertEqual(counter["called"], 1)
        # No extra duplicate database records
        self.assertEqual(InboundWebhookEvent.objects.count(), 1)

    def test_invalid_signatures_are_rejected_and_auditable(self):
        payload = {"action": "tampered"}
        event_id = "gh-delivery-uuid-invalid"

        ack, outcome, record = process_inbound_webhook(
            provider="github",
            event_id=event_id,
            event_type="push",
            payload=payload,
            signature_valid=False,
        )
        self.assertFalse(ack)
        self.assertEqual(outcome, "invalid_signature")

        # Record is saved with status='rejected' for auditability
        audit_event = InboundWebhookEvent.objects.get(event_id=event_id)
        self.assertEqual(audit_event.status, "rejected")
        self.assertFalse(audit_event.signature_valid)
        self.assertIn("Invalid webhook signature", audit_event.failure_reason)

    def test_out_of_order_events_explicit_policy(self):
        now = timezone.now()
        t1 = now - datetime.timedelta(minutes=10)
        t2 = now - datetime.timedelta(minutes=5)

        # Event 2 arrived first (timestamp t2)
        ack2, outcome2, _ = process_inbound_webhook(
            provider="github",
            event_id="delivery-2",
            event_type="issue.updated",
            payload={"issue": 42, "state": "closed"},
            signature_valid=True,
            event_timestamp=t2,
            out_of_order_policy="reject",
        )
        self.assertTrue(ack2)
        self.assertEqual(outcome2, "processed")

        # Delayed Event 1 arrives later (timestamp t1 < t2)
        ack1, outcome1, record1 = process_inbound_webhook(
            provider="github",
            event_id="delivery-1",
            event_type="issue.updated",
            payload={"issue": 42, "state": "open"},
            signature_valid=True,
            event_timestamp=t1,
            out_of_order_policy="reject",
        )
        self.assertFalse(ack1)
        self.assertEqual(outcome1, "out_of_order_rejected")
        self.assertEqual(record1.status, "out_of_order")
        self.assertIn("Out-of-order event", record1.failure_reason)

    def test_guarded_operator_replay(self):
        # Create an event that failed processing originally
        event = InboundWebhookEvent.objects.create(
            provider="github",
            event_id="delivery-failed-1",
            event_type="pull_request",
            payload={"action": "opened"},
            signature_valid=True,
            status="failed",
            failure_reason="Temporary database deadlock",
        )

        # Replay without operator argument fails
        with self.assertRaises(CommandError):
            call_command("replay_inbound_webhook", id=event.id, operator="")

        # Replay with valid operator succeeds
        call_command(
            "replay_inbound_webhook", id=event.id, operator="admin_alice"
        )
        event.refresh_from_db()
        self.assertTrue(event.replayed)
        self.assertEqual(event.replayed_by, "admin_alice")
        self.assertIsNotNone(event.replayed_at)
        self.assertEqual(event.status, "processed")
        self.assertEqual(event.failure_reason, "")

    def test_cannot_replay_invalid_signature_event(self):
        event = InboundWebhookEvent.objects.create(
            provider="github",
            event_id="delivery-fake-1",
            event_type="pull_request",
            payload={},
            signature_valid=False,
            status="rejected",
        )

        # Guarded replay rejects events with invalid signatures
        with self.assertRaises(CommandError):
            call_command(
                "replay_inbound_webhook", id=event.id, operator="admin_bob"
            )
