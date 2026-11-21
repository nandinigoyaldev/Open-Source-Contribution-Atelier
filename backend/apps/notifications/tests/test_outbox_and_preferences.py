import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from pywebpush import WebPushException

from apps.notifications.channels.base import DeliveryResult
from apps.notifications.channels.push_channel import PushChannel
from apps.notifications.delivery import make_dedupe_key
from apps.notifications.models import (
    Notification,
    NotificationAttempt,
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationPreference,
    PushSubscription,
)
from apps.notifications.tasks import (
    dispatch_notification,
    send_bulk_email,
    send_web_push_notification,
)

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="outbox_tester",
        email="outbox_tester@example.com",
        password="securepass123",
    )


@pytest.fixture
def push_sub(test_user):
    return PushSubscription.objects.create(
        user=test_user,
        endpoint="https://push.example.test/sub/123",
        p256dh="test_p256dh_key",
        auth="test_auth_key",
    )


def fake_webpush_error(status_code):
    err = WebPushException(f"Simulated HTTP {status_code}")
    err.response = SimpleNamespace(status_code=status_code)
    return err


@pytest.mark.django_db
def test_web_push_outbox_success_lifecycle(test_user, push_sub):
    """Successful web push creates a NotificationDelivery outbox record with status 'sent'."""
    with override_settings(
        VAPID_PRIVATE_KEY="test_key", VAPID_ADMIN_EMAIL="test@example.com"
    ):
        with patch("apps.notifications.tasks.webpush", return_value=None):
            send_web_push_notification(
                user_id=test_user.id,
                title="Level 3 Test",
                message="Testing outbox lifecycle",
                url="/app/dashboard",
            )

    deliveries = NotificationDelivery.objects.filter(
        recipient=test_user, channel="push"
    )
    assert deliveries.count() == 1
    delivery = deliveries.first()
    assert delivery.status == "sent"
    assert delivery.sent_at is not None
    assert delivery.provider == "webpush"
    assert delivery.dedupe_key is not None
    assert delivery.attempts.count() == 1
    assert delivery.attempts.first().outcome == "sent"


@pytest.mark.django_db
def test_web_push_deduplication_prevents_duplicate_sends(test_user, push_sub):
    """Re-executing web push with identical content/dedupe_key is idempotent and does not send twice."""
    with override_settings(
        VAPID_PRIVATE_KEY="test_key", VAPID_ADMIN_EMAIL="test@example.com"
    ):
        with patch("apps.notifications.tasks.webpush", return_value=None) as mock_push:
            send_web_push_notification(test_user.id, "Welcome", "Welcome to OSCA")
            assert mock_push.call_count == 1

            # Second call with identical payload must be deduplicated
            send_web_push_notification(test_user.id, "Welcome", "Welcome to OSCA")
            assert mock_push.call_count == 1

    deliveries = NotificationDelivery.objects.filter(
        recipient=test_user, channel="push"
    )
    assert deliveries.count() == 1
    assert deliveries.first().status == "sent"


@pytest.mark.django_db
def test_web_push_transient_failure_retries_with_backoff(test_user, push_sub):
    """Transient failures (e.g. 503 Service Unavailable) record attempt and schedule backoff retry."""
    with override_settings(
        VAPID_PRIVATE_KEY="test_key", VAPID_ADMIN_EMAIL="test@example.com"
    ):
        with patch(
            "apps.notifications.tasks.webpush", side_effect=fake_webpush_error(503)
        ):
            send_web_push_notification(
                test_user.id, "Transient", "Testing transient error"
            )

    delivery = NotificationDelivery.objects.get(recipient=test_user, channel="push")
    assert delivery.status == "pending"
    assert delivery.retry_count == 1
    assert delivery.next_retry_at is not None
    assert delivery.error_class == "transient"
    assert "503" in delivery.error_message
    assert delivery.attempts.count() == 1
    assert delivery.attempts.first().outcome == "transient_failure"


@pytest.mark.django_db
def test_web_push_permanent_410_retires_endpoint(test_user, push_sub):
    """Permanent endpoint failures (410 Gone / 404 Not Found) remove the subscription and retire endpoint."""
    sub_id = push_sub.id
    with override_settings(
        VAPID_PRIVATE_KEY="test_key", VAPID_ADMIN_EMAIL="test@example.com"
    ):
        with patch(
            "apps.notifications.tasks.webpush", side_effect=fake_webpush_error(410)
        ):
            send_web_push_notification(test_user.id, "Gone", "Subscription expired")

    assert not PushSubscription.objects.filter(id=sub_id).exists()
    delivery = NotificationDelivery.objects.get(recipient=test_user, channel="push")
    assert delivery.status == "failed"
    assert delivery.error_class == "permanent"
    assert NotificationDeadLetter.objects.filter(recipient=test_user).exists()


@pytest.mark.django_db
def test_email_outbox_deduplication_and_idempotency(test_user):
    """Bulk email outbox ensures each recipient gets exactly one delivery with a dedupe key."""
    mail.outbox = []
    payload = {
        "template_id": "badge_earned_email",
        "recipients": [test_user.email],
        "data": {
            "badge_name": "Open Source Hero",
            "username": test_user.username,
        },
    }

    send_bulk_email(payload)
    assert len(mail.outbox) == 1

    delivery = NotificationDelivery.objects.get(recipient=test_user, channel="email")
    assert delivery.status == "sent"
    assert delivery.sent_at is not None
    assert delivery.attempts.count() == 1
    assert delivery.attempts.first().outcome == "sent"

    # Retrying same bulk email task does not duplicate sends
    send_bulk_email(payload)
    assert len(mail.outbox) == 1
    assert (
        NotificationDelivery.objects.filter(
            recipient=test_user, channel="email"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_user_can_disable_channel_without_affecting_in_app(test_user, push_sub):
    """Disabling email and push channels respects user opt-outs while in-app notifications still deliver."""
    mail.outbox = []
    prefs, _ = NotificationPreference.objects.get_or_create(user=test_user)
    prefs.email_enabled = False
    prefs.in_app_enabled = True
    # Disable push across all categories
    for cat in prefs.channel_preferences:
        prefs.channel_preferences[cat]["push"] = False
    prefs.save()

    with override_settings(
        VAPID_PRIVATE_KEY="test_key", VAPID_ADMIN_EMAIL="test@example.com"
    ):
        with patch("apps.notifications.tasks.webpush") as mock_push:
            # 1. Direct webpush should be skipped due to opt-out
            send_web_push_notification(test_user.id, "Push", "Opted out push")
            mock_push.assert_not_called()

            # 2. Bulk email should be skipped due to opt-out
            send_bulk_email(
                {
                    "template_id": "badge_earned_email",
                    "recipients": [test_user.email],
                    "data": {
                        "badge_name": "Fast Learner",
                        "username": test_user.username,
                    },
                }
            )
            assert len(mail.outbox) == 0

            # 3. Dispatch notification should generate an in-app notification successfully
            deliveries = dispatch_notification(
                recipient=test_user,
                notif_type="badge",
                title="In-App Badge",
                message="Earned badge in-app",
                dedupe_key=make_dedupe_key("test_in_app", test_user.id),
            )

    notifs = Notification.objects.filter(recipient=test_user)
    assert notifs.count() == 1
    assert notifs.first().title == "In-App Badge"
    in_app_deliv = NotificationDelivery.objects.filter(
        recipient=test_user, channel="in_app"
    )
    assert in_app_deliv.exists()
