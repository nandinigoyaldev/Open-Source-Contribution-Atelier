import hashlib
import hmac
import json
import logging

import requests
from celery import shared_task
from django.utils import timezone

from .models import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)


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
        # Check if the endpoint is subscribed to this event
        if event_type in endpoint.events or "*" in endpoint.events:
            delivery = WebhookDelivery.objects.create(
                endpoint=endpoint,
                event_type=event_type,
                payload=payload,
                status="pending",
            )
            # Dispatch asynchronously
            deliver_webhook.delay(delivery.id)


@shared_task(bind=True, max_retries=3)
def deliver_webhook(self, delivery_id):
    try:
        delivery = WebhookDelivery.objects.get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return

    endpoint = delivery.endpoint
    signature = generate_signature(delivery.payload, endpoint.secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": delivery.event_type,
    }

    try:
        response = requests.post(
            endpoint.target_url, json=delivery.payload, headers=headers, timeout=10
        )
        delivery.status_code = response.status_code
        delivery.response_body = response.text[:2000]  # limit stored response size

        if 200 <= response.status_code < 300:
            delivery.status = "success"
        elif response.status_code == 429 or response.status_code >= 500:
            # Trigger retry for rate limits and server errors
            raise requests.exceptions.RequestException(
                f"Recoverable error: {response.status_code}"
            )
        else:
            # 4xx errors (except 429) are client errors, do not retry
            delivery.status = "failed"

    except requests.exceptions.RequestException as e:
        delivery.response_body = str(e)[:2000]

        # Retry with exponential backoff
        try:
            self.retry(exc=e, countdown=2**self.request.retries * 60)
        except self.MaxRetriesExceededError:
            delivery.status = "failed"
            logger.error(f"Max retries exceeded for webhook delivery {delivery.id}")
    finally:
        delivery.save()
