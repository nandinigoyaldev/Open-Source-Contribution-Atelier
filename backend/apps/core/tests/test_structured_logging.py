import json
import logging
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.core.logging import (
    PIIRedactionFilter,
    StructuredJsonFormatter,
    get_trace_correlation,
    redact_pii,
)
from apps.core.middleware.request_id import _thread_locals


class StructuredJsonFormatterTests(SimpleTestCase):
    def setUp(self):
        self.formatter = StructuredJsonFormatter(service_name="test-atelier-service")
        # Clear thread locals
        _thread_locals.request_id = None
        _thread_locals.correlation_id = None
        _thread_locals.user_id = None
        _thread_locals.duration_ms = None

    def tearDown(self):
        _thread_locals.request_id = None
        _thread_locals.correlation_id = None
        _thread_locals.user_id = None
        _thread_locals.duration_ms = None

    def _create_record(self, msg, level=logging.INFO, **kwargs):
        record = logging.LogRecord(
            name="apps.core.test",
            level=level,
            pathname=__file__,
            lineno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in kwargs.items():
            setattr(record, k, v)
        return record

    def test_standard_fields_emitted_in_json(self):
        record = self._create_record("User initiated learning session")
        output = self.formatter.format(record)

        data = json.loads(output)
        expected_fields = [
            "timestamp",
            "level",
            "trace_id",
            "span_id",
            "user_id",
            "service",
            "duration_ms",
            "message",
        ]
        for field in expected_fields:
            self.assertIn(field, data)

        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["service"], "test-atelier-service")
        self.assertEqual(data["message"], "User initiated learning session")

    def test_request_id_correlation_injected(self):
        _thread_locals.request_id = "req-xyz-987654"
        _thread_locals.user_id = 42
        _thread_locals.duration_ms = 125.45

        record = self._create_record("API request completed")
        data = json.loads(self.formatter.format(record))

        self.assertEqual(data["trace_id"], "req-xyz-987654")
        self.assertEqual(data["user_id"], "42")
        self.assertEqual(data["duration_ms"], 125.45)

    def test_opentelemetry_trace_and_span_correlation(self):
        # Mock active OpenTelemetry span context
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x4BF92F3577B34DA6A3CE929D0E0E4736
        mock_span_context.span_id = 0x00F067AA0BA902B7

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            trace_id, span_id = get_trace_correlation()
            self.assertEqual(trace_id, "4bf92f3577b34da6a3ce929d0e0e4736")
            self.assertEqual(span_id, "00f067aa0ba902b7")

            record = self._create_record("Distributed span operation")
            data = json.loads(self.formatter.format(record))
            self.assertEqual(data["trace_id"], "4bf92f3577b34da6a3ce929d0e0e4736")
            self.assertEqual(data["span_id"], "00f067aa0ba902b7")

    def test_pii_redaction_passwords_and_tokens(self):
        secret_msg = (
            "Connecting with password=SuperSecretPassword123! and "
            "token: abcd1234efgh5678 and Authorization: Bearer secret-auth-token-xyz"
        )
        record = self._create_record(secret_msg)
        data = json.loads(self.formatter.format(record))

        self.assertNotIn("SuperSecretPassword123!", data["message"])
        self.assertNotIn("secret-auth-token-xyz", data["message"])
        self.assertIn("[REDACTED]", data["message"])

    def test_pii_redaction_jwt_and_credit_card_digits(self):
        jwt_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        card_num_hyphenated = "4111-2222-3333-4444"
        card_num_raw = "1234567890123456"

        raw_msg = (
            f"User session {jwt_token} processed billing card {card_num_hyphenated} "
            f"and secondary {card_num_raw}"
        )
        record = self._create_record(raw_msg)
        data = json.loads(self.formatter.format(record))

        self.assertNotIn(jwt_token, data["message"])
        self.assertNotIn(card_num_hyphenated, data["message"])
        self.assertNotIn(card_num_raw, data["message"])
        self.assertIn("[REDACTED_JWT]", data["message"])
        self.assertIn("[REDACTED_CARD]", data["message"])

    def test_pii_redaction_filter(self):
        pii_filter = PIIRedactionFilter()
        record = self._create_record(
            "User password=hunter2 with card 4532-1234-5678-9010"
        )
        result = pii_filter.filter(record)

        self.assertTrue(result)
        self.assertNotIn("hunter2", record.msg)
        self.assertNotIn("4532-1234-5678-9010", record.msg)
        self.assertIn("[REDACTED]", record.msg)
        self.assertIn("[REDACTED_CARD]", record.msg)
