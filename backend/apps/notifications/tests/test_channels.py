import hmac
import hashlib
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notifications.channels.base import (
    get_registered_channels,
    get_channel_instance,
)
from apps.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationDeadLetter,
    NotificationPreference,
)
from apps.notifications.rate_limiter import ChannelRateLimiter
from apps.notifications.tasks import (
    dispatch_notification,
    process_notification_delivery,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="Password123!",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="adminuser",
        email="admin@example.com",
        password="Password123!",
    )


@pytest.mark.django_db
class TestNotificationChannels:

    def test_registered_channels_include_slack(self):
        registered = get_registered_channels()
        assert "in_app" in registered
        assert "email" in registered
        assert "push" in registered
        assert "sms" in registered
        assert "webhook" in registered
        assert "slack" in registered
        assert get_channel_instance("slack") is not None

    def test_end_to_end_dispatch_in_app_and_email(self, user):
        deliveries = dispatch_notification(
            recipient=user,
            notif_type="badge",
            title="🏅 Test Badge",
            message="You earned a test badge",
        )
        assert len(deliveries) >= 2
        in_app_d = next(d for d in deliveries if d.channel == "in_app")
        email_d = next(d for d in deliveries if d.channel == "email")

        assert in_app_d.status == "sent"
        assert email_d.status == "sent"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["testuser@example.com"]
        assert (
            "track/open" in mail.outbox[0].body
            or "track/open" in mail.outbox[0].alternatives[0][0]
        )

    def test_webhook_channel_hmac_signature(self, user):
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        pref.webhook_url = "https://webhook.site/test-endpoint"
        pref.webhook_secret = "secret123"
        pref.channel_preferences = {"badge": {"webhook": True, "in_app": False}}
        pref.save()

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            deliveries = dispatch_notification(
                recipient=user,
                notif_type="badge",
                title="Webhook Alert",
                message="Test payload",
            )
            webhook_d = next(d for d in deliveries if d.channel == "webhook")
            assert webhook_d.status == "sent"

            assert mock_post.called
            _, kwargs = mock_post.call_args
            headers = kwargs["headers"]
            assert "X-Signature-256" in headers

            body_json = kwargs["data"]
            expected_sig = hmac.new(
                b"secret123", body_json.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            assert headers["X-Signature-256"] == f"sha256={expected_sig}"

    def test_sms_channel(self, user):
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        pref.phone_number = "+15005550006"
        pref.channel_preferences = {"badge": {"sms": True}}
        pref.save()

        deliveries = dispatch_notification(
            recipient=user,
            notif_type="badge",
            title="SMS Alert",
            message="Test SMS",
        )
        sms_d = next(d for d in deliveries if d.channel == "sms")
        assert sms_d.status == "sent"

    def test_rate_limiting(self, user):
        for _ in range(10):
            allowed, _ = ChannelRateLimiter.is_allowed(
                user.id, "email", max_requests=3, window_seconds=60
            )

        # 11th call should be blocked
        allowed, _ = ChannelRateLimiter.is_allowed(
            user.id, "email", max_requests=3, window_seconds=60
        )
        assert allowed is False

    def test_retry_and_dead_letter_queue(self, user):
        delivery = NotificationDelivery.objects.create(
            recipient=user,
            channel="webhook",
            status="pending",
        )
        payload = {"title": "Failing", "message": "Failed"}

        with patch(
            "apps.notifications.channels.webhook_channel.WebhookChannel.deliver",
            side_effect=RuntimeError("Connection refused"),
        ):
            for _ in range(3):
                process_notification_delivery(delivery.id, payload)
                delivery.refresh_from_db()

        assert delivery.status == "failed"
        assert delivery.retry_count == 3
        dead_letter = NotificationDeadLetter.objects.filter(
            recipient=user, channel="webhook"
        ).first()
        assert dead_letter is not None
        assert "Connection refused" in dead_letter.error_message

    def test_tracking_pixel_and_click(self, user):
        client = APIClient()
        delivery = NotificationDelivery.objects.create(
            recipient=user,
            channel="email",
            status="sent",
        )

        # Track open
        res_open = client.get(f"/api/notifications/track/open/{delivery.id}/")
        assert res_open.status_code == 200
        assert res_open["Content-Type"] == "image/gif"
        delivery.refresh_from_db()
        assert delivery.status == "opened"

        # Track click
        res_click = client.get(
            f"/api/notifications/track/click/{delivery.id}/?target=https://example.com"
        )
        assert res_click.status_code == 302
        assert res_click.url == "https://example.com"
        delivery.refresh_from_db()
        assert delivery.status == "clicked"

    def test_channels_settings_api(self, user):
        client = APIClient()
        client.force_authenticate(user=user)

        res = client.get("/api/notifications/channels/")
        assert res.status_code == 200
        assert "available_channels" in res.data
        assert "slack" in res.data["available_channels"]

        updated_data = {
            "channel_preferences": {
                "badge": {
                    "in_app": True,
                    "email": False,
                    "push": True,
                    "sms": True,
                    "webhook": False,
                    "slack": True,
                }
            },
            "phone_number": "+19998887777",
            "webhook_url": "https://webhook.site/my-hook",
        }
        put_res = client.put(
            "/api/notifications/channels/", data=updated_data, format="json"
        )
        assert put_res.status_code == 200
        assert put_res.data["phone_number"] == "+19998887777"
        assert put_res.data["channel_preferences"]["badge"]["email"] is False

    def test_admin_metrics_load_time(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)

        t0 = time.time()
        res = client.get("/api/notifications/admin/metrics/")
        t1 = time.time()

        assert res.status_code == 200
        assert (t1 - t0) < 2.0
        assert "total_deliveries" in res.data
        assert "success_rate_percentage" in res.data
        assert "channel_breakdown" in res.data
