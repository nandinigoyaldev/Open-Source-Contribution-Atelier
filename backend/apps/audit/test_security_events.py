from typing import Any
from unittest.mock import patch

import pytest

from apps.audit.models import AuditEvent
from apps.audit.redaction import REDACTED
from apps.audit.security_events import record_security_event

Events: Any = AuditEvent._default_manager


def record(**overrides: Any) -> Any:
    fields: dict = {
        "operation": "password_reset.failed",
        "target_type": "auth.user",
        "target_id": 7,
    }
    fields.update(overrides)
    return record_security_event(**fields)


@pytest.mark.django_db
class TestRecordSecurityEvent:
    def test_shape(self):
        event = record(
            payload={"reason": "unknown_token"},
            ip_address="203.0.113.5",
            user_agent="agent",
            request_id="abc",
        )

        event = Events.get(pk=event.pk)
        assert event.action == AuditEvent.ACTION_CREATED
        assert event.resource_type == "auth.user"
        assert event.resource_id == "7"
        assert event.actor is None
        assert event.ip_address == "203.0.113.5"
        assert event.user_agent == "agent"
        assert event.correlation_id == "abc"
        assert event.extra == {
            "source": "security",
            "operation": "password_reset.failed",
            "payload": {"reason": "unknown_token"},
        }

    def test_payload_is_redacted(self):
        event = record(payload={"token": "1b4e28ba", "note": "ok"})

        assert event.extra["payload"] == {"token": REDACTED, "note": "ok"}

    @pytest.mark.parametrize("value", ["", None, "not-an-address", "1.2.3.4.5"])
    def test_a_bad_address_is_dropped_not_fatal(self, value):
        assert record(ip_address=value).ip_address is None

    def test_long_values_are_cut_to_fit(self):
        event = record(user_agent="a" * 600, request_id="b" * 100, target_id="c" * 80)

        assert len(event.user_agent) == 512
        assert len(event.correlation_id) == 64
        assert len(event.resource_id) == 64

    def test_a_failed_write_returns_none(self):
        with patch(
            "apps.audit.security_events.AuditEvent._default_manager.create",
            side_effect=RuntimeError("boom"),
        ):
            assert record() is None
