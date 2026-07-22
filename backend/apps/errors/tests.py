from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from django.urls import reverse
from unittest.mock import patch

from apps.errors.models import ErrorGroup, ErrorEvent
from apps.errors.grouping import normalize_message, calculate_fingerprint
from apps.errors.tasks import ingest_error_event_task


class NormalizationTests(TestCase):
    def test_normalize_ips(self):
        msg1 = "Connection refused to 127.0.0.1:6379"
        msg2 = "Connection refused to 10.0.0.1:6379"
        self.assertEqual(normalize_message(msg1), "Connection refused to <IP>:6379")
        self.assertEqual(normalize_message(msg2), "Connection refused to <IP>:6379")

        # IPv6
        self.assertEqual(
            normalize_message(
                "Failed to connect to 2001:db8:3333:4444:5555:6666:7777:8888"
            ),
            "Failed to connect to <IP>",
        )

    def test_normalize_uuids(self):
        msg = "Resource 123e4567-e89b-12d3-a456-426614174000 not found"
        self.assertEqual(normalize_message(msg), "Resource <UUID> not found")

    def test_normalize_emails(self):
        msg = "Failed verification for user.name+test@example.com"
        self.assertEqual(normalize_message(msg), "Failed verification for <EMAIL>")

    def test_normalize_timestamps(self):
        msg1 = "Error occurred at 2026-07-16T14:30:00Z"
        msg2 = "Error occurred at 2026-07-16 14:30:00.123456+05:30"
        self.assertEqual(normalize_message(msg1), "Error occurred at <TIMESTAMP>")
        self.assertEqual(normalize_message(msg2), "Error occurred at <TIMESTAMP>")

    def test_normalize_user_ids(self):
        self.assertEqual(
            normalize_message("Failed for user_id=123"), "Failed for <USER_ID>"
        )
        self.assertEqual(
            normalize_message("Failed for User #456"), "Failed for <USER_ID>"
        )
        self.assertEqual(
            normalize_message("Failed for user/789"), "Failed for <USER_ID>"
        )


class FingerprintTests(TestCase):
    def test_fingerprint_generation(self):
        msg = "Connection refused to 127.0.0.1:6379"
        norm = normalize_message(msg)
        fp = calculate_fingerprint(
            norm, 'Traceback:\n  File "app.py", line 12\n    run()', "redis"
        )

        # Test line number changes do not change fingerprint
        fp_different_line = calculate_fingerprint(
            norm, 'Traceback:\n  File "app.py", line 99\n    run()', "redis"
        )
        self.assertEqual(fp, fp_different_line)


class ErrorIngestionTaskTests(TestCase):
    def test_event_grouping(self):
        payload1 = {
            "message": "Connection refused to 127.0.0.1:6379",
            "module": "redis",
        }
        payload2 = {"message": "Connection refused to 10.0.0.1:6379", "module": "redis"}

        event1_id = ingest_error_event_task(payload1)
        event2_id = ingest_error_event_task(payload2)

        event1 = ErrorEvent.objects.get(id=event1_id)
        event2 = ErrorEvent.objects.get(id=event2_id)

        self.assertEqual(event1.group, event2.group)
        self.assertEqual(event1.group.count, 2)

    def test_resolved_auto_reopen_cooldown(self):
        payload = {"message": "Database is down", "module": "db"}
        event_id = ingest_error_event_task(payload)
        event = ErrorEvent.objects.get(id=event_id)
        group = event.group

        # Resolve group
        group.status = "resolved"
        group.resolved_at = timezone.now()
        group.save()

        # Ingest within 7 days - should NOT reopen
        ingest_error_event_task(payload)
        group.refresh_from_db()
        self.assertEqual(group.status, "resolved")

        # Fake resolved_at to be 8 days ago
        group.resolved_at = timezone.now() - timedelta(days=8)
        group.save()

        # Ingest now - should reopen
        ingest_error_event_task(payload)
        group.refresh_from_db()
        self.assertEqual(group.status, "new")
        self.assertIsNone(group.resolved_at)


class ErrorAPIEndpointTests(APITestCase):
    @patch("apps.errors.views.ingest_error_event_task.delay")
    def test_ingestion_endpoint(self, mock_delay):
        url = reverse("error-ingest")
        payload = {
            "message": "Division by zero",
            "stacktrace": "Traceback...",
            "module": "math",
            "user_id": "42",
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data, {"status": "queued"})
        mock_delay.assert_called_once_with(payload)
