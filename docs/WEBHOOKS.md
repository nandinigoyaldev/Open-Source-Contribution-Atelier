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
To ensure that webhooks are legitimately sent from our platform and have not been tampered with, every webhook request includes an `X-Webhook-Signature` header. 

The signature is an HMAC SHA-256 hash generated using your endpoint's unique `secret` and the raw request body.

### Verification Example (Python):
```python
import hmac
import hashlib
import json

def verify_signature(payload_body, secret_token, header_signature):
    # Ensure payload_body is the exact raw bytes received
    expected_sig = hmac.new(
        secret_token.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_sig, header_signature)
```

## 4. Webhook API Specifications
- **List Endpoints**: `GET /api/webhooks/endpoints/`
- **Retrieve Endpoint**: `GET /api/webhooks/endpoints/{id}/`
- **Update Endpoint**: `PATCH /api/webhooks/endpoints/{id}/`
- **Delete Endpoint**: `DELETE /api/webhooks/endpoints/{id}/`
- **List Deliveries**: `GET /api/webhooks/deliveries/` (View history of webhook dispatches and their statuses).

## 5. Delivery and Retry Behavior
Our event dispatch service utilizes Celery for asynchronous processing, ensuring reliable delivery without blocking the main application flow.
- **Timeouts**: Webhook delivery requests will timeout after 10 seconds.
- **Retries**: If a delivery fails (e.g., timeout, network error, or an HTTP 5xx response), it will be retried automatically using exponential backoff up to 3 times.
- **Failures**: Persistent failures can be reviewed via the Deliveries API (`/api/webhooks/deliveries/`), where the HTTP status code and response body snippet are logged.

## 6. Guidelines for Integrating Third-Party Services
1. **Idempotency**: Webhooks may occasionally be delivered more than once. Ensure your event handlers are idempotent.
2. **Response Time**: Respond to webhook requests quickly (with a `2xx` status code). Offload heavy processing to your own asynchronous queues to prevent timeouts.
3. **Security**: Always validate the `X-Webhook-Signature` header to prevent spoofing attacks. Use HTTPS for your `target_url` to ensure payloads are encrypted in transit.
