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
    @patch("apps.webhooks.tasks.deliver_webhook.delay")
    def test_event_triggering(self, mock_delay, endpoint):
        dispatch_event("test.event", {"hello": "world"})
        assert WebhookDelivery.objects.count() == 1
        delivery = WebhookDelivery.objects.first()
        assert delivery.event_type == "test.event"
        assert delivery.payload == {"hello": "world"}
        mock_delay.assert_called_once_with(delivery.id)

    @patch("apps.webhooks.tasks.deliver_webhook.delay")
    def test_no_dispatch_if_not_subscribed(self, mock_delay, endpoint):
        dispatch_event("other.event", {"hello": "world"})
        assert WebhookDelivery.objects.count() == 0
        mock_delay.assert_not_called()

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
    @patch("apps.webhooks.tasks.deliver_webhook.retry")
    def test_retry_behavior(self, mock_retry, mock_post, endpoint):
        import requests

        mock_post.side_effect = requests.exceptions.RequestException("Timeout")

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id)

        delivery.refresh_from_db()
        assert delivery.status == "pending"
        mock_retry.assert_called_once()

    @patch("apps.webhooks.tasks.deliver_webhook.retry")
    @patch("requests.post")
    def test_retry_on_429(self, mock_post, mock_retry, endpoint):
        from celery.exceptions import Retry

        mock_retry.side_effect = Retry()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_post.return_value = mock_response

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )

        with pytest.raises(Retry):
            deliver_webhook(delivery.id)

        delivery.refresh_from_db()
        assert delivery.status == "pending"
        assert delivery.status_code == 429

    @patch("requests.post")
    @patch("apps.webhooks.tasks.deliver_webhook.retry")
    def test_max_retries_exceeded(self, mock_retry, mock_post, endpoint):
        import requests
        from celery.exceptions import MaxRetriesExceededError

        mock_post.side_effect = requests.exceptions.RequestException("Timeout")
        mock_retry.side_effect = MaxRetriesExceededError()

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint, event_type="test.event", payload={"foo": "bar"}
        )
        deliver_webhook(delivery.id)

        delivery.refresh_from_db()
        assert delivery.status == "failed"
        mock_retry.assert_called_once()
