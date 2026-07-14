import hashlib
import hmac
import json
import logging

import requests
from django.utils import timezone
from django_q.tasks import async_task

from .models import DeadLetterWebhook, WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)

# Maximum number of delivery attempts before moving to the Dead Letter Queue.
MAX_RETRIES = 5

# Base delay in seconds. Actual delay = BASE_DELAY_SECONDS * 2^(attempt-1)
# Attempt 1 → 60s, 2 → 120s, 3 → 240s, 4 → 480s, 5 → 960s (~16 min)
BASE_DELAY_SECONDS = 60


def _exponential_backoff(attempt: int) -> int:
    """Return the countdown in seconds for the given attempt number (1-indexed)."""
    return BASE_DELAY_SECONDS * (2 ** (attempt - 1))


def generate_signature(payload, secret):
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    secret_bytes = secret.encode("utf-8")
    return hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()


def dispatch_event(event_type, payload):
    """
    Finds all active webhooks subscribed to the given event_type
    and queues delivery tasks.
    """
    endpoints = WebhookEndpoint.objects.filter(is_active=True)
    for endpoint in endpoints:
        if event_type in endpoint.events or "*" in endpoint.events:
            delivery = WebhookDelivery.objects.create(
                endpoint=endpoint,
                event_type=event_type,
                payload=payload,
                status="pending",
                attempt_count=0,
            )
            async_task(
                "apps.webhooks.tasks.deliver_webhook",
                delivery.id,
                attempt=1,
            )


def _move_to_dlq(delivery: WebhookDelivery, reason: str) -> None:
    """Move a permanently failed delivery to the Dead Letter Queue."""
    delivery.status = "dead"
    delivery.save(update_fields=["status", "updated_at"])
    DeadLetterWebhook.objects.get_or_create(
        delivery=delivery,
        defaults={"reason": reason},
    )
    logger.error(
        "Webhook delivery %s moved to DLQ after %d attempts. Reason: %s",
        delivery.id,
        delivery.attempt_count,
        reason,
    )


def deliver_webhook(delivery_id, attempt=1):
    """
    Attempt to deliver a webhook payload. On failure, schedules a retry with
    exponential backoff. After MAX_RETRIES exhausted, moves the delivery to
    the Dead Letter Queue (DeadLetterWebhook).
    """
    try:
        delivery = WebhookDelivery.objects.get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        logger.warning("deliver_webhook: delivery %s not found, skipping.", delivery_id)
        return

    endpoint = delivery.endpoint
    signature = generate_signature(delivery.payload, endpoint.secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Attempt": str(attempt),
    }

    delivery.attempt_count = attempt
    delivery.status = "retrying" if attempt > 1 else "pending"

    try:
        response = requests.post(
            endpoint.target_url, json=delivery.payload, headers=headers, timeout=10
        )
        delivery.status_code = response.status_code
        delivery.response_body = response.text[:2000]

        if 200 <= response.status_code < 300:
            delivery.status = "success"
            delivery.next_retry_at = None
            delivery.save()
            return

        # Retryable: rate-limited or server-side errors
        is_retryable = response.status_code == 429 or response.status_code >= 500
        failure_reason = f"HTTP {response.status_code}: {response.text[:500]}"

    except requests.exceptions.RequestException as exc:
        is_retryable = True
        failure_reason = str(exc)[:1000]
        delivery.response_body = failure_reason

    # --- Schedule retry or move to DLQ ---
    if is_retryable and attempt < MAX_RETRIES:
        countdown = _exponential_backoff(attempt)
        delivery.status = "retrying"
        delivery.next_retry_at = timezone.now() + timezone.timedelta(seconds=countdown)
        delivery.save()

        async_task(
            "apps.webhooks.tasks.deliver_webhook",
            delivery_id,
            attempt=attempt + 1,
            q_options={"timeout": countdown + 30},
        )
        logger.warning(
            "Webhook delivery %s attempt %d failed (%s). Retrying in %ds.",
            delivery_id,
            attempt,
            failure_reason[:100],
            countdown,
        )
    else:
        delivery.save()
        _move_to_dlq(delivery, failure_reason)


def replay_delivery(dlq_entry_id: int) -> None:
    """
    Requeue a dead-lettered webhook delivery for a fresh attempt.
    Called by the replay_dead_webhooks management command or admin action.
    """
    try:
        dlq = DeadLetterWebhook.objects.select_related("delivery").get(id=dlq_entry_id)
    except DeadLetterWebhook.DoesNotExist:
        logger.error("replay_delivery: DLQ entry %s not found.", dlq_entry_id)
        return

    delivery = dlq.delivery
    # Reset for a fresh delivery cycle
    delivery.status = "pending"
    delivery.attempt_count = 0
    delivery.next_retry_at = None
    delivery.save(update_fields=["status", "attempt_count", "next_retry_at", "updated_at"])

    dlq.replayed = True
    dlq.replayed_at = timezone.now()
    dlq.save(update_fields=["replayed", "replayed_at"])

    async_task("apps.webhooks.tasks.deliver_webhook", delivery.id, attempt=1)
    logger.info("Queued replay for DLQ entry %s (delivery %s).", dlq_entry_id, delivery.id)
