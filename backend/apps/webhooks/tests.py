import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
from apps.webhooks.tasks import deliver_webhook, dispatch_event, generate_signature

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
        from apps.webhooks.security import verify_signature, compute_signature

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
