import json

import pytest
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

from apps.webhooks.security import (
    compute_signature,
    require_webhook_signature,
    verify_signature,
)

SECRET = "my_super_secret_key"
PAYLOAD = json.dumps({"event": "user.signup", "id": 123}).encode("utf-8")
VALID_SIGNATURE = compute_signature(SECRET, PAYLOAD)


def dummy_view(request):
    return JsonResponse({"status": "ok"})


@pytest.fixture
def rf():
    return RequestFactory()


def test_compute_signature():
    sig = compute_signature("test_secret", b"test_payload")
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex digest length


def test_verify_signature_valid():
    assert verify_signature(SECRET, PAYLOAD, VALID_SIGNATURE) is True


def test_verify_signature_invalid():
    assert verify_signature(SECRET, PAYLOAD, "invalid_signature") is False


def test_verify_signature_missing():
    assert verify_signature(SECRET, PAYLOAD, "") is False
    assert verify_signature(SECRET, PAYLOAD, None) is False


def test_decorator_valid_signature(rf):
    decorated_view = require_webhook_signature(SECRET)(dummy_view)
    request = rf.post(
        "/webhook/",
        data=PAYLOAD,
        content_type="application/json",
        HTTP_X_SIGNATURE=VALID_SIGNATURE,
    )
    response = decorated_view(request)
    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


def test_decorator_invalid_signature(rf):
    decorated_view = require_webhook_signature(SECRET)(dummy_view)
    request = rf.post(
        "/webhook/",
        data=PAYLOAD,
        content_type="application/json",
        HTTP_X_SIGNATURE="bad_signature",
    )
    response = decorated_view(request)
    assert response.status_code == 403
    assert json.loads(response.content) == {"error": "Invalid signature"}


def test_decorator_missing_header(rf):
    decorated_view = require_webhook_signature(SECRET)(dummy_view)
    request = rf.post(
        "/webhook/",
        data=PAYLOAD,
        content_type="application/json",
        # No signature header
    )
    response = decorated_view(request)
    assert response.status_code == 403
    assert json.loads(response.content) == {"error": "Missing signature header"}


def test_decorator_empty_payload(rf):
    decorated_view = require_webhook_signature(SECRET)(dummy_view)
    request = rf.post(
        "/webhook/",
        data=b"",
        content_type="application/json",
        HTTP_X_SIGNATURE=VALID_SIGNATURE,
    )
    response = decorated_view(request)
    assert response.status_code == 400
    assert json.loads(response.content) == {"error": "Empty payload"}


def test_decorator_callable_secret(rf):
    def get_secret(request):
        return "dynamic_secret"

    dynamic_payload = b"dynamic_data"
    dynamic_sig = compute_signature("dynamic_secret", dynamic_payload)

    decorated_view = require_webhook_signature(get_secret)(dummy_view)
    request = rf.post(
        "/webhook/",
        data=dynamic_payload,
        content_type="application/json",
        HTTP_X_SIGNATURE=dynamic_sig,
    )
    response = decorated_view(request)
    assert response.status_code == 200


def test_decorator_custom_header(rf):
    decorated_view = require_webhook_signature(SECRET, header_name="HTTP_X_CUSTOM_SIG")(
        dummy_view
    )
    request = rf.post(
        "/webhook/",
        data=PAYLOAD,
        content_type="application/json",
        HTTP_X_CUSTOM_SIG=VALID_SIGNATURE,
    )
    response = decorated_view(request)
    assert response.status_code == 200
