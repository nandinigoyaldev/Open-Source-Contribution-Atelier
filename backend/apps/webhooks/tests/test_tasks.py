# backend/apps/webhooks/tests/test_tasks.py
import json
import hmac
import hashlib
import responses
from backend.apps.webhooks.tasks import deliver_webhook

class MockEndpoint:
    def __init__(self, url, secret):
        self.url = url
        self.secret = secret

@responses.activate
def test_webhook_delivery_includes_hmac_signature():
    target_url = "https://example.com/webhook"
    secret_key = "test-secret-key"
    payload = {"event": "ping", "data": {"id": 123}}

    endpoint = MockEndpoint(url=target_url, secret=secret_key)

    # Mock the external POST request
    responses.add(
        responses.POST,
        target_url,
        status=200,
        json={"success": True}
    )

    success = deliver_webhook(endpoint, payload)
    assert success is True

    # Verify signature in sent request headers
    request_call = responses.calls[0]
    sent_body = request_call.request.body
    sent_signature_header = request_call.request.headers.get("X-Atelier-Signature")

    # Compute expected signature manually
    expected_sig = hmac.new(
        secret_key.encode('utf-8'),
        sent_body,
        hashlib.sha256
    ).hexdigest()

    assert sent_signature_header == f"sha256={expected_sig}"
