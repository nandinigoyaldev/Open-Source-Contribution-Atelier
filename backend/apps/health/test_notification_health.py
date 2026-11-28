"""
Tests for the "Notification Delivery" health check (retry exhaustion).
"""

from datetime import timedelta

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.health.views import HealthChecker, _minimal_response
from apps.notifications.models import NotificationDeadLetter

# The count runs in a worker thread, so the rows have to be committed.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _limits(settings):
    settings.NOTIFICATION_DEAD_LETTER_HEALTH_THRESHOLD = 3
    settings.NOTIFICATION_DEAD_LETTER_HEALTH_WINDOW_SECONDS = 600


@pytest.fixture
def recipient():
    return get_user_model().objects.create_user(
        username="dead-letter", email="dead-letter@example.com", password="x-12345678"
    )


def _dead_letter(recipient, channel="email", age_seconds=0):
    row = NotificationDeadLetter.objects.create(
        recipient=recipient,
        channel=channel,
        retry_count=3,
        error_message="secret error text",
        payload={"body": "secret message body"},
    )
    if age_seconds:
        NotificationDeadLetter.objects.filter(pk=row.pk).update(
            failed_at=timezone.now() - timedelta(seconds=age_seconds)
        )


def _check():
    return async_to_sync(HealthChecker().check_notification_delivery)()


def test_no_failures_is_healthy():
    result = _check()

    assert result["status"] == "healthy"
    assert result["details"]["terminal_failures"] == 0
    assert result["details"]["by_channel"] == {}


def test_failures_accumulate_until_the_threshold(recipient):
    _dead_letter(recipient, "email")
    _dead_letter(recipient, "sms")
    below = _check()

    _dead_letter(recipient, "email")
    at = _check()

    assert below["status"] == "healthy"
    assert below["details"]["terminal_failures"] == 2
    assert at["status"] == "unhealthy"
    assert at["details"]["terminal_failures"] == 3
    assert at["details"]["by_channel"] == {"email": 2, "sms": 1}
    assert at["details"]["threshold"] == 3
    assert at["details"]["runbook"].endswith("#retry-exhaustion-health")


def test_count_resets_once_failures_leave_the_window(recipient):
    for _ in range(4):
        _dead_letter(recipient, age_seconds=601)

    result = _check()

    assert result["status"] == "healthy"
    assert result["details"]["terminal_failures"] == 0
    # The check only reads; history is left to the retention purge.
    assert NotificationDeadLetter.objects.count() == 4


def test_result_never_contains_message_content(recipient):
    for _ in range(3):
        _dead_letter(recipient)

    result = _check()

    text = str(result)
    assert "secret" not in text
    assert recipient.email not in text
    minimal = _minimal_response(
        {
            "status": "degraded",
            "timestamp": 0,
            "checks": {result["name"]: result},
        }
    )
    assert minimal["checks"][result["name"]] == {
        "name": "Notification Delivery",
        "status": "unhealthy",
    }


def test_zero_threshold_turns_the_check_off(recipient, settings):
    settings.NOTIFICATION_DEAD_LETTER_HEALTH_THRESHOLD = 0
    _dead_letter(recipient)

    assert _check()["status"] == "not_configured"
