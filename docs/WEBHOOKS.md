# Webhooks Integration Guide

The Open-Source Contribution Atelier platform provides a robust webhook infrastructure, allowing organizations and third-party services to receive real-time HTTP push notifications when specific events occur within the application.

## 1. Webhook Registration Workflow
Webhooks can be managed via the REST API using the `/api/webhooks/endpoints/` endpoint. You must be authenticated to register or manage webhooks.

### Create a Webhook Endpoint
**POST** `/api/webhooks/endpoints/`
```json
{
  "target_url": "https://your-service.com/webhook",
  "events": ["lesson.completed", "user.signup"],
  "is_active": true
}
```
*Note: Use `["*"]` to subscribe to all events.*

Upon creation, the API will return a `secret` token. **Store this secret securely**, as it is required to verify the authenticity of incoming webhook payloads.

## 2. Event Payload Format
All webhooks are dispatched as `POST` requests with a `Content-Type: application/json` header. The payload is the raw JSON representation of the event context.

Example Event Payload:
```json
{
  "event": "lesson.completed",
  "user_id": 123,
  "lesson_id": 456,
  "timestamp": "2026-06-22T12:00:00Z",
  "data": {
    "score": 100
  }
}
```

## 3. Signature Verification Process
To ensure that webhooks are legitimately sent from our platform, have not been tampered with and are not an old request sent again, every delivery carries these headers:

| Header | Value |
| --- | --- |
| `X-Webhook-Timestamp` | Unix time (whole seconds) when this attempt was signed. Every retry gets a fresh one. |
| `X-Webhook-Signature-V2` | `sha256=<hex>`, an HMAC SHA-256 of `"<timestamp>." + raw body`, keyed with your endpoint `secret`. |
| `X-Webhook-Signature` | The older signature: hex HMAC SHA-256 of the raw body only. Still sent for one more release (see below). |

The body is compact JSON (`separators=(",", ":")`) and is sent exactly as it was signed, so verify against the raw bytes you received, not a re-serialized copy.

### Verification Example (Python):
```python
import hashlib
import hmac
import re
import time

TOLERANCE_SECONDS = 300


def verify_webhook(payload_body: bytes, secret_token: str, headers) -> bool:
    # payload_body must be the exact raw bytes received
    timestamp = headers.get("X-Webhook-Timestamp", "")
    signature = headers.get("X-Webhook-Signature-V2", "")

    if not re.fullmatch(r"[0-9]{1,12}", timestamp):
        return False
    if abs(time.time() - int(timestamp)) > TOLERANCE_SECONDS:
        return False  # too old (replay) or too far in the future
    if not re.fullmatch(r"(sha256=)?[0-9a-f]{64}", signature):
        return False

    expected = hmac.new(
        secret_token.encode("utf-8"),
        timestamp.encode("ascii") + b"." + payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected.encode(), signature.removeprefix("sha256=").encode())
```

### Moving off the old header
`X-Webhook-Signature` (payload-only) cannot detect a replay: anyone who captured one request can send it again later. It is still sent so existing receivers keep working. Switch to `X-Webhook-Signature-V2`, then set `WEBHOOK_SEND_LEGACY_SIGNATURE = False` on the sender.

### Settings
| Setting | Default | Meaning |
| --- | --- | --- |
| `WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS` | `300` | Largest accepted difference between the request timestamp and the server clock, in both directions. (`WEBHOOK_TIMESTAMP_WINDOW_SECONDS` is the old name and is used if the new one is not set.) |
| `WEBHOOK_ALLOW_LEGACY_SIGNATURES` | `True` | Incoming endpoints also accept payload-only signatures. A request that arrives this way is written to the `audit` log as `webhook.legacy_signature_accepted` so you can see when nobody uses it any more. **Set it to `False` as soon as your senders use timestamped signatures.** While it is `True`, a captured payload-only request can still be replayed. The default is meant to go to `False` in the release after this one. |
| `WEBHOOK_SEND_LEGACY_SIGNATURE` | `True` | Outgoing deliveries still carry `X-Webhook-Signature`. |
| `WEBHOOK_SIGNING_KEYS` | none | List of `(key_id, secret)` pairs for incoming endpoints, active key first. With no key configured incoming verification fails closed (HTTP 500); only `DEBUG=True` falls back to a throwaway development key. |

Incoming endpoints also accept an optional `X-Webhook-Key-Id`. A sender that names a key the server does not know is rejected, and a known id limits verification to that one key.

Rejected requests are written to the `audit` logger as one JSON line (`event`, `reason`, `source`, `path`, `remote_addr`, `key_id`, `timestamp`, `skew_seconds`). The secret, the signature and the body are never logged. See [WEBHOOK_THREAT_MODEL.md](WEBHOOK_THREAT_MODEL.md) for what is and is not covered.

## 4. Webhook API Specifications
- **List Endpoints**: `GET /api/webhooks/endpoints/`
- **Retrieve Endpoint**: `GET /api/webhooks/endpoints/{id}/`
- **Update Endpoint**: `PATCH /api/webhooks/endpoints/{id}/`
- **Delete Endpoint**: `DELETE /api/webhooks/endpoints/{id}/`
- **List Deliveries**: `GET /api/webhooks/deliveries/` (View history of webhook dispatches and their statuses).
- **Retry a failed delivery**: `POST /api/webhooks/deliveries/{id}/replay/`. Only the owner of the endpoint can call it (another signed-in user gets a `404`, an anonymous caller a `401`). It works on a delivery that is `failed` or `dead`; for any other status, including one that is already being retried, it answers `409` with the current status, so a double click sends the webhook once. The response has the refreshed `delivery`.

## 5. Delivery and Retry Behavior
Our event dispatch service utilizes Celery for asynchronous processing, ensuring reliable delivery without blocking the main application flow.
- **Timeouts**: Webhook delivery requests will timeout after 10 seconds.
- **Retries**: If a delivery fails (e.g., timeout, network error, or an HTTP 5xx response), it will be retried automatically using exponential backoff up to 3 times.
- **Duplicate dispatches**: callers of `dispatch_event` can pass a `dedupe_key`. Dispatching the same key to the same endpoint again does not create a second delivery (the built-in lesson, badge, XP, issue and PR signals do this). A queued task that runs twice, or a retry that was already handled, is skipped instead of POSTing again.
- **Failures**: Persistent failures can be reviewed via the Deliveries API (`/api/webhooks/deliveries/`), where the HTTP status code and response body snippet are logged.

## 6. Guidelines for Integrating Third-Party Services
1. **Idempotency**: Webhooks may occasionally be delivered more than once. Ensure your event handlers are idempotent. Every request carries an `X-Webhook-Delivery-Id` header. It is the same value on every retry and on a replay from the dead letter queue, so store it and ignore a request whose id you have already processed.
2. **Response Time**: Respond to webhook requests quickly (with a `2xx` status code). Offload heavy processing to your own asynchronous queues to prevent timeouts.
3. **Security**: Always validate the `X-Webhook-Signature-V2` header and the timestamp window to prevent spoofing and replay attacks. Use HTTPS for your `target_url` to ensure payloads are encrypted in transit.
