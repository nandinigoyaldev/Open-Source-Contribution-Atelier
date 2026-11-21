import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.webhooks.models import DeadLetterWebhook, WebhookDelivery, WebhookEndpoint
from apps.webhooks.tasks import (
    deliver_webhook,
    dispatch_event,
    generate_signature,
    replay_delivery,
)

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="password123")


@pytest.fixture
def endpoint(user):
    return WebhookEndpoint.objects.create(
        user=user, target_url="https://example.com/webhook", events=["test.event"]
    )


@pytest.mark.django_db
class TestWebhookCRUD:
    def test_create_webhook(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/webhooks/endpoints/",
            {"target_url": "https://example.com/hook", "events": ["user.created"]},
            format="json",
        )
        assert response.status_code == 201
        assert response.data["target_url"] == "https://example.com/hook"
        assert response.data["secret"] is not None

    def test_update_webhook(self, api_client, user, endpoint):
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            f"/api/webhooks/endpoints/{endpoint.id}/",
            {"is_active": False},
            format="json",
        )
        assert response.status_code == 200
        endpoint.refresh_from_db()
        assert not endpoint.is_active

    def test_delete_webhook(self, api_client, user, endpoint):
        api_client.force_authenticate(user=user)
        response = api_client.delete(f"/api/webhooks/endpoints/{endpoint.id}/")
        assert response.status_code == 204
        assert WebhookEndpoint.objects.count() == 0

    def test_permission_enforcement(self, api_client, endpoint):
        # Unauthenticated request
        response = api_client.get(f"/api/webhooks/endpoints/")
        assert response.status_code == 401

        # Another user cannot see first user's webhook
        other_user = User.objects.create_user(username="other", password="pw")
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f"/api/webhooks/endpoints/")
        assert response.status_code == 200
        assert len(response.data) == 0


@pytest.mark.django_db
class TestWebhookDelivery:
    @patch("apps.webhooks.tasks.async_task")
    def test_event_triggering(self, mock_async_task, endpoint):
        dispatch_event("test.event", {"hello": "world"})
        assert WebhookDelivery.objects.count() == 1
        delivery = WebhookDelivery.objects.first()
        assert delivery.event_type == "test.event"
        assert delivery.payload == {"hello": "world"}
        mock_async_task.assert_called_once_with(
            "apps.webhooks.tasks.deliver_webhook",
            delivery.id,
            attempt=1,
        )

    @patch("apps.webhooks.tasks.async_task")
    def test_no_dispatch_if_not_subscribed(self, mock_async_task, endpoint):
        dispatch_event("other.event", {"hello": "world"})
        assert WebhookDelivery.objects.count() == 0
        mock_async_task.assert_not_called()

    def test_signature_validation(self):
        payload = {"data": "test"}
        secret = "supersecret"
        sig = generate_signature(payload, secret)
        expected = hmac.new(
            b"supersecret", b'{"data":"test"}', hashlib.sha256
        ).hexdigest()
        assert sig == expected

    @patch("requests.post")
    def test_delivery_success(self, mock_post, endpoint):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        assert delivery.status_code == 200
        assert delivery.response_body == "OK"

        # Verify headers
        args, kwargs = mock_post.call_args
        assert "X-Webhook-Signature" in kwargs["headers"]

    @patch("requests.post")
    @patch("apps.webhooks.tasks.async_task")
    def test_retry_behavior(self, mock_async_task, mock_post, endpoint):
        import requests

        mock_post.side_effect = requests.exceptions.RequestException("Timeout")

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id, attempt=1)

        delivery.refresh_from_db()
        assert delivery.status == "retrying"
        mock_async_task.assert_called_once_with(
            "apps.webhooks.tasks.deliver_webhook",
            delivery.id,
            attempt=2,
            q_options={"timeout": 90},
        )

    @patch("requests.post")
    @patch("apps.webhooks.tasks.async_task")
    def test_retry_on_429(self, mock_async_task, mock_post, endpoint):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_post.return_value = mock_response

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )

        deliver_webhook(delivery.id, attempt=1)

        delivery.refresh_from_db()
        assert delivery.status == "retrying"
        assert delivery.status_code == 429
        mock_async_task.assert_called_once_with(
            "apps.webhooks.tasks.deliver_webhook",
            delivery.id,
            attempt=2,
            q_options={"timeout": 90},
        )

    @patch("requests.post")
    @patch("apps.webhooks.tasks.async_task")
    def test_max_retries_exceeded(self, mock_async_task, mock_post, endpoint):
        import requests

        mock_post.side_effect = requests.exceptions.RequestException("Timeout")

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id, attempt=5)

        delivery.refresh_from_db()
        assert delivery.status == "dead"
        mock_async_task.assert_not_called()


@pytest.mark.django_db
class TestWebhookIdempotency:
    @patch("apps.webhooks.tasks.async_task")
    def test_same_dedupe_key_creates_one_delivery(self, mock_async_task, endpoint):
        dispatch_event("test.event", {"id": 1}, dedupe_key="test.event:1")
        dispatch_event("test.event", {"id": 1}, dedupe_key="test.event:1")

        assert WebhookDelivery.objects.count() == 1
        mock_async_task.assert_called_once()

    @patch("apps.webhooks.tasks.async_task")
    def test_different_dedupe_keys_create_separate_deliveries(
        self, mock_async_task, endpoint
    ):
        dispatch_event("test.event", {"id": 1}, dedupe_key="test.event:1")
        dispatch_event("test.event", {"id": 2}, dedupe_key="test.event:2")

        assert WebhookDelivery.objects.count() == 2
        assert mock_async_task.call_count == 2

    @patch("apps.webhooks.tasks.async_task")
    def test_dedupe_key_is_scoped_per_endpoint(self, mock_async_task, user, endpoint):
        other = WebhookEndpoint.objects.create(
            user=user, target_url="https://example.org/hook", events=["test.event"]
        )
        dispatch_event("test.event", {"id": 1}, dedupe_key="test.event:1")

        assert WebhookDelivery.objects.filter(endpoint=endpoint).count() == 1
        assert WebhookDelivery.objects.filter(endpoint=other).count() == 1

    @patch("apps.webhooks.tasks.async_task")
    def test_no_dedupe_key_keeps_old_behaviour(self, mock_async_task, endpoint):
        dispatch_event("test.event", {"id": 1})
        dispatch_event("test.event", {"id": 1})

        assert WebhookDelivery.objects.count() == 2
        assert mock_async_task.call_count == 2

    @patch("requests.post")
    def test_delivery_id_header_is_sent(self, mock_post, endpoint):
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id)

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-Webhook-Delivery-Id"] == str(delivery.id)

    @patch("requests.post")
    def test_duplicate_task_after_success_does_not_post_again(
        self, mock_post, endpoint
    ):
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id, attempt=1)
        deliver_webhook(delivery.id, attempt=1)

        assert mock_post.call_count == 1
        delivery.refresh_from_db()
        assert delivery.status == "success"

    @patch("requests.post")
    @patch("apps.webhooks.tasks.async_task")
    def test_duplicate_retry_task_does_not_post_again(
        self, mock_async_task, mock_post, endpoint
    ):
        mock_post.return_value = MagicMock(status_code=500, text="boom")
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id, attempt=1)
        # the queue hands the same attempt-1 task over a second time
        deliver_webhook(delivery.id, attempt=1)

        assert mock_post.call_count == 1
        mock_async_task.assert_called_once()

    @patch("requests.post")
    def test_dead_delivery_is_not_sent(self, mock_post, endpoint):
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type="test.event",
            payload={"foo": "bar"},
            status="dead",
        )
        deliver_webhook(delivery.id, attempt=2)

        mock_post.assert_not_called()

    @patch("requests.post")
    @patch("apps.webhooks.tasks.async_task")
    def test_replay_still_sends_with_same_delivery_id(
        self, mock_async_task, mock_post, endpoint
    ):
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type="test.event",
            payload={"foo": "bar"},
            status="dead",
            attempt_count=5,
        )
        dlq = DeadLetterWebhook.objects.create(delivery=delivery, reason="HTTP 500")

        replay_delivery(dlq.id)
        deliver_webhook(delivery.id, attempt=1)

        mock_post.assert_called_once()
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-Webhook-Delivery-Id"] == str(delivery.id)
        delivery.refresh_from_db()
        assert delivery.status == "success"


@pytest.mark.django_db
class TestWebhookSecretSecurity:
    def test_secret_encryption_at_rest(self, endpoint):
        # Retrieve raw database value to ensure encryption-at-rest
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT encrypted_secret FROM webhooks_webhookendpoint WHERE id = %s",
                [endpoint.id],
            )
            row = cursor.fetchone()
            encrypted_val = row[0]
            assert encrypted_val is not None
            assert encrypted_val != endpoint.secret

    def test_secret_not_in_get_or_update(self, api_client, user, endpoint):
        api_client.force_authenticate(user=user)

        # GET retrieve
        res = api_client.get(f"/api/webhooks/endpoints/{endpoint.id}/")
        assert res.status_code == 200
        assert "secret" not in res.data

        # GET list
        res = api_client.get("/api/webhooks/endpoints/")
        assert res.status_code == 200
        assert len(res.data) > 0
        assert "secret" not in res.data[0]

        # PATCH update
        res = api_client.patch(
            f"/api/webhooks/endpoints/{endpoint.id}/",
            {"is_active": False},
            format="json",
        )
        assert res.status_code == 200
        assert "secret" not in res.data

    def test_secret_rotation(self, api_client, user, endpoint):
        api_client.force_authenticate(user=user)
        old_secret = endpoint.secret

        # Call rotate endpoint
        res = api_client.post(f"/api/webhooks/endpoints/{endpoint.id}/rotate/")
        assert res.status_code == 200
        assert res.data["status"] == "success"
        new_secret = res.data["secret"]
        assert new_secret is not None
        assert new_secret != old_secret

        endpoint.refresh_from_db()
        assert endpoint.secret == new_secret
        from apps.webhooks.security import decrypt_secret

        assert decrypt_secret(endpoint.encrypted_old_secret) == old_secret
        assert endpoint.old_secret_expires_at is not None

    def test_verify_signature_rotation_grace_period(self, endpoint):
        from django.utils import timezone

        from apps.webhooks.security import compute_signature, verify_signature

        payload = b"test_payload"
        old_secret = endpoint.secret
        sig_old = compute_signature(old_secret, payload)

        # Rotate secret manually
        endpoint.encrypted_old_secret = endpoint.encrypted_secret
        endpoint.old_secret_expires_at = timezone.now() + timezone.timedelta(hours=24)
        new_secret = "newly_rotated_secret_123"
        endpoint.secret = new_secret
        endpoint.save()

        sig_new = compute_signature(new_secret, payload)

        # Retrieve valid secrets list
        valid_secrets = endpoint.get_valid_secrets()
        assert len(valid_secrets) == 2
        assert old_secret in valid_secrets
        assert new_secret in valid_secrets

        # Verify both signatures work
        assert verify_signature(valid_secrets, payload, sig_new) is True
        assert verify_signature(valid_secrets, payload, sig_old) is True

        # Expire old secret
        endpoint.old_secret_expires_at = timezone.now() - timezone.timedelta(seconds=1)
        endpoint.save()

        valid_secrets_expired = endpoint.get_valid_secrets()
        assert len(valid_secrets_expired) == 1
        assert old_secret not in valid_secrets_expired

        # Verify old signature no longer works
        assert verify_signature(valid_secrets_expired, payload, sig_old) is False
        assert verify_signature(valid_secrets_expired, payload, sig_new) is True

    @patch("apps.cache.audit_logger.AuditLogger.log")
    def test_audit_logging_events(self, mock_audit_log, api_client, user, endpoint):
        api_client.force_authenticate(user=user)

        # Test creation logging
        res = api_client.post(
            "/api/webhooks/endpoints/",
            {"target_url": "https://example.com/audit", "events": ["test.audit"]},
            format="json",
        )
        assert res.status_code == 201

        created_calls = [
            c
            for c in mock_audit_log.mock_calls
            if c[2].get("action") == "secret_created"
        ]
        assert len(created_calls) > 0
        assert created_calls[0][2].get("user_id") == str(user.id)

        # Test rotation logging
        res = api_client.post(f"/api/webhooks/endpoints/{endpoint.id}/rotate/")
        assert res.status_code == 200

        rotated_calls = [
            c
            for c in mock_audit_log.mock_calls
            if c[2].get("action") == "secret_rotated"
        ]
        assert len(rotated_calls) > 0
        assert rotated_calls[0][2].get("user_id") == str(user.id)
        assert rotated_calls[0][2].get("resource_id") == str(endpoint.id)


@pytest.mark.django_db
class TestWebhookDirectTestAndSignals:
    @patch("requests.post")
    def test_direct_webhook_test_endpoint(self, mock_post, api_client, user):
        api_client.force_authenticate(user=user)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"ok": true}'
        mock_post.return_value = mock_resp

        response = api_client.post(
            "/api/webhooks/test/",
            {
                "target_url": "https://httpbin.org/post",
                "secret": "my_secret",
                "event": "lesson.completed",
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["status_code"] == 200

    @patch("apps.webhooks.tasks.dispatch_event")
    def test_webhook_signal_handlers(self, mock_dispatch):
        from apps.progress.models import XPEvent
        from apps.webhooks.signals import webhook_on_xp_milestone

        xp_instance = MagicMock(spec=XPEvent)
        xp_instance.user_id = 1
        xp_instance.user.username = "alice"
        xp_instance.xp_delta = 50
        xp_instance.source_type = "lesson"
        xp_instance.description = "Completed lesson"
        xp_instance.created_at = None

        webhook_on_xp_milestone(XPEvent, xp_instance, created=True)
        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args[0][0] == "xp.milestone"


@pytest.mark.django_db
class TestWebhookCircuitBreaker:
    def test_record_failure_and_trip_circuit(self, endpoint):
        assert endpoint.health_status == "healthy"
        assert endpoint.is_circuit_open() is False

        # Record failures below threshold (threshold=5)
        for i in range(4):
            endpoint.record_failure(f"Error {i}")
            assert endpoint.consecutive_failure_count == i + 1
            assert endpoint.health_status == "healthy"
            assert endpoint.is_circuit_open() is False

        # 5th failure trips the circuit
        endpoint.record_failure("Threshold error")
        assert endpoint.consecutive_failure_count == 5
        assert endpoint.health_status == "degraded"
        assert endpoint.is_circuit_open() is True
        assert endpoint.circuit_broken_until is not None
        assert endpoint.is_half_open() is False
        assert endpoint.circuit_state == "OPEN"

    def test_record_failure_escalation_to_suspended(self, endpoint):
        endpoint.failure_threshold = 3
        endpoint.save()

        # 3 failures -> degraded
        for _ in range(3):
            endpoint.record_failure("Err")
        assert endpoint.health_status == "degraded"

        # 3 * 3 = 9 failures -> suspended
        for _ in range(6):
            endpoint.record_failure("Err")
        assert endpoint.consecutive_failure_count == 9
        assert endpoint.health_status == "suspended"
        assert endpoint.is_circuit_open() is True
        assert endpoint.circuit_state == "SUSPENDED"

    def test_record_success_resets_circuit(self, endpoint):
        endpoint.record_failure("Err 1")
        endpoint.record_failure("Err 2")
        endpoint.health_status = "degraded"
        endpoint.circuit_broken_until = timezone.now() + timezone.timedelta(minutes=15)
        endpoint.save()

        endpoint.record_success()
        assert endpoint.health_status == "healthy"
        assert endpoint.consecutive_failure_count == 0
        assert endpoint.circuit_broken_until is None
        assert endpoint.last_failure_reason == ""
        assert endpoint.is_circuit_open() is False
        assert endpoint.circuit_state == "CLOSED"

    def test_half_open_probe_transition(self, endpoint):
        endpoint.health_status = "degraded"
        endpoint.consecutive_failure_count = 5
        # Set cooldown in the past
        endpoint.circuit_broken_until = timezone.now() - timezone.timedelta(seconds=10)
        endpoint.save()

        assert endpoint.is_half_open() is True
        assert endpoint.circuit_state == "HALF_OPEN"
        # While half-open, is_circuit_open allows trial probe
        assert endpoint.is_circuit_open() is False

    @patch("apps.webhooks.tasks.async_task")
    def test_dispatch_event_fast_fails_open_circuit(self, mock_async, endpoint):
        endpoint.health_status = "degraded"
        endpoint.circuit_broken_until = timezone.now() + timezone.timedelta(minutes=10)
        endpoint.save()

        from apps.webhooks.tasks import dispatch_event

        dispatch_event("test.event", {"test": 123})

        # async_task should NOT be called (worker bypassed)
        mock_async.assert_not_called()

        delivery = WebhookDelivery.objects.filter(endpoint=endpoint).first()
        assert delivery is not None
        assert delivery.status == "failed"
        assert "Circuit open" in delivery.response_body

    @patch("requests.post")
    def test_deliver_webhook_half_open_success_recovers_circuit(
        self, mock_post, endpoint
    ):
        endpoint.health_status = "degraded"
        endpoint.consecutive_failure_count = 5
        endpoint.circuit_broken_until = timezone.now() - timezone.timedelta(seconds=1)
        endpoint.save()

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type="test.event",
            payload={"msg": "probe"},
            status="pending",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "ok"}'
        mock_post.return_value = mock_resp

        deliver_webhook(delivery.id, attempt=1)

        delivery.refresh_from_db()
        endpoint.refresh_from_db()

        assert delivery.status == "success"
        assert endpoint.health_status == "healthy"
        assert endpoint.consecutive_failure_count == 0
        assert endpoint.circuit_broken_until is None

    def test_reset_circuit_api_action(self, api_client, user, endpoint):
        api_client.force_authenticate(user=user)
        endpoint.health_status = "degraded"
        endpoint.consecutive_failure_count = 5
        endpoint.circuit_broken_until = timezone.now() + timezone.timedelta(minutes=15)
        endpoint.save()

        res = api_client.post(f"/api/webhooks/endpoints/{endpoint.id}/reset-circuit/")
        assert res.status_code == 200
        assert res.data["status"] == "success"
        assert res.data["health_status"] == "healthy"
        assert res.data["consecutive_failure_count"] == 0

        endpoint.refresh_from_db()
        assert endpoint.health_status == "healthy"
        assert endpoint.consecutive_failure_count == 0
        assert endpoint.circuit_broken_until is None

    def test_serializer_exposes_circuit_fields(self, api_client, user, endpoint):
        api_client.force_authenticate(user=user)
        res = api_client.get(f"/api/webhooks/endpoints/{endpoint.id}/")
        assert res.status_code == 200
        data = res.data
        assert "health_status" in data
        assert "consecutive_failure_count" in data
        assert "circuit_broken_until" in data
        assert "is_circuit_open" in data
        assert "circuit_state" in data
        assert data["health_status"] == "healthy"
        assert data["circuit_state"] == "CLOSED"
        assert data["is_circuit_open"] is False
