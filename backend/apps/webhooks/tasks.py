import hashlib
import hmac
import json
import logging

import requests
from django_q.tasks import async_task

from .models import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)

# Maximum number of delivery attempts before giving up.
MAX_RETRIES = 3


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
            # Dispatch asynchronously — start with attempt=1
            async_task(
                "apps.webhooks.tasks.deliver_webhook",
                delivery.id,
                attempt=1,
            )


def deliver_webhook(delivery_id, attempt=1):
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
            # Recoverable: retry with exponential backoff up to MAX_RETRIES
            if attempt < MAX_RETRIES:
                countdown = 2**attempt * 60  # 2min, 4min, ...
                async_task(
                    "apps.webhooks.tasks.deliver_webhook",
                    delivery_id,
                    attempt=attempt + 1,
                    q_options={"timeout": countdown + 30},
                )
                delivery.status = "pending"
            else:
                delivery.status = "failed"
                logger.error(
                    "Max retries exceeded for webhook delivery %s", delivery.id
                )
        else:
            # 4xx errors (except 429) are client errors — do not retry
            delivery.status = "failed"

    except requests.exceptions.RequestException as e:
        delivery.response_body = str(e)[:2000]
        if attempt < MAX_RETRIES:
            countdown = 2**attempt * 60
            async_task(
                "apps.webhooks.tasks.deliver_webhook",
                delivery_id,
                attempt=attempt + 1,
                q_options={"timeout": countdown + 30},
            )
            delivery.status = "pending"
        else:
            delivery.status = "failed"
            logger.error(
                "Max retries exceeded for webhook delivery %s: %s", delivery.id, e
            )
    finally:
        delivery.save()
