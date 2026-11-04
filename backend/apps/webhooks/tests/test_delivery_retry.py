from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.webhooks.models import DeadLetterWebhook, WebhookDelivery, WebhookEndpoint

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(username="hook-owner", password="pw12345!")


@pytest.fixture
def stranger():
    return User.objects.create_user(username="hook-stranger", password="pw12345!")


@pytest.fixture
def endpoint(owner):
    return WebhookEndpoint._default_manager.create(
        user=owner, target_url="https://example.com/hook", events=["test.event"]
    )


def api_client(user=None) -> Any:
    """APIClient typed as Any: without django-stubs Pyright types its responses as WSGIRequest."""
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


@pytest.fixture
def owner_client(owner):
    return api_client(owner)


def make_delivery(endpoint, status="failed", **extra):
    return WebhookDelivery._default_manager.create(
        endpoint=endpoint,
        event_type="test.event",
        payload={"hello": "world"},
        status=status,
        status_code=500,
        response_body="boom",
        attempt_count=extra.pop("attempt_count", 3),
        **extra,
    )


def url(delivery):
    return f"/api/webhooks/deliveries/{delivery.id}/replay/"


def ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "OK"
    return resp


@pytest.mark.django_db
class TestRetryFailedDelivery:
    @patch("apps.webhooks.tasks.requests.post")
    def test_owner_can_retry_a_failed_delivery(self, mock_post, owner_client, endpoint):
        mock_post.return_value = ok_response()
        delivery = make_delivery(endpoint, "failed")

        res = owner_client.post(url(delivery))

        assert res.status_code == 200
        assert res.data["delivery"]["id"] == delivery.id
        assert res.data["delivery"]["status"] == "success"
        delivery.refresh_from_db()
        assert delivery.status == "success"
        assert delivery.attempt_count == 1
        assert mock_post.call_count == 1
        # same id on the retry, so the receiver can drop duplicates
        assert mock_post.call_args.kwargs["headers"]["X-Webhook-Delivery-Id"] == str(
            delivery.id
        )

    @patch("apps.webhooks.tasks.requests.post")
    def test_dead_letter_delivery_can_be_retried_and_is_marked(
        self, mock_post, owner_client, endpoint
    ):
        mock_post.return_value = ok_response()
        delivery = make_delivery(endpoint, "dead")
        dlq = DeadLetterWebhook._default_manager.create(
            delivery=delivery, reason="HTTP 500"
        )

        res = owner_client.post(url(delivery))

        assert res.status_code == 200
        assert res.data["delivery"]["status"] == "success"
        dlq.refresh_from_db()
        assert dlq.replayed is True
        assert dlq.replayed_at is not None

    @patch("apps.webhooks.tasks.async_task")
    @patch("apps.webhooks.tasks.requests.post")
    def test_retry_that_fails_again_returns_the_new_status(
        self, mock_post, mock_async, owner_client, endpoint
    ):
        bad = MagicMock()
        bad.status_code = 503
        bad.text = "unavailable"
        mock_post.return_value = bad
        delivery = make_delivery(endpoint, "failed")

        res = owner_client.post(url(delivery))

        assert res.status_code == 200
        assert res.data["delivery"]["status"] == "retrying"
        assert res.data["delivery"]["status_code"] == 503

    @pytest.mark.parametrize("state", ["success", "pending", "retrying"])
    @patch("apps.webhooks.tasks.requests.post")
    def test_only_failed_deliveries_can_be_retried(
        self, mock_post, state, owner_client, endpoint
    ):
        delivery = make_delivery(endpoint, state)

        res = owner_client.post(url(delivery))

        assert res.status_code == 409
        assert res.data["status"] == state
        assert "Only failed or dead deliveries" in res.data["error"]
        mock_post.assert_not_called()
        delivery.refresh_from_db()
        assert delivery.status == state
        assert delivery.attempt_count == 3  # untouched

    @patch("apps.webhooks.views.deliver_webhook")
    @patch("apps.webhooks.tasks.requests.post")
    def test_second_click_while_the_first_is_in_flight_is_a_409(
        self, mock_post, mock_deliver, owner_client, endpoint
    ):
        # deliver_webhook is stubbed, so the delivery stays "pending" the way it
        # does while the first request is still waiting on the receiver.
        delivery = make_delivery(endpoint, "failed")

        first = owner_client.post(url(delivery))
        second = owner_client.post(url(delivery))

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.data["status"] == "pending"
        assert mock_deliver.call_count == 1

    @patch("apps.webhooks.tasks.requests.post")
    def test_second_click_after_a_successful_retry_is_a_409(
        self, mock_post, owner_client, endpoint
    ):
        mock_post.return_value = ok_response()
        delivery = make_delivery(endpoint, "failed")

        assert owner_client.post(url(delivery)).status_code == 200
        assert owner_client.post(url(delivery)).status_code == 409
        assert mock_post.call_count == 1


@pytest.mark.django_db
class TestRetryAccess:
    @patch("apps.webhooks.tasks.requests.post")
    def test_another_user_cannot_retry(self, mock_post, stranger, endpoint):
        delivery = make_delivery(endpoint, "failed")
        client = api_client(stranger)

        res = client.post(url(delivery))

        assert res.status_code == 404
        mock_post.assert_not_called()
        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert delivery.attempt_count == 3

    @patch("apps.webhooks.tasks.requests.post")
    def test_anonymous_user_is_rejected(self, mock_post, endpoint):
        delivery = make_delivery(endpoint, "failed")

        res = api_client().post(url(delivery))

        assert res.status_code == 401
        mock_post.assert_not_called()
        delivery.refresh_from_db()
        assert delivery.status == "failed"

    def test_unknown_delivery_is_a_404(self, owner_client):
        assert (
            owner_client.post("/api/webhooks/deliveries/999999/replay/").status_code
            == 404
        )

    def test_retry_is_post_only(self, owner_client, endpoint):
        delivery = make_delivery(endpoint, "failed")
        assert owner_client.get(url(delivery)).status_code == 405
