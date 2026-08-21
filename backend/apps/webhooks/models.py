import hashlib
import hmac
import json
import logging
import requests

logger = logging.getLogger(__name__)


def send_webhook_delivery(delivery_id: int):
    """
    Retrieves a webhook delivery, computes the HMAC SHA256 signature 
    using the endpoint's secret, attaches the X-Atelier-Signature header, 
    and posts the payload to the target URL.
    """
    from apps.webhooks.models import WebhookDelivery

    try:
        delivery = WebhookDelivery.objects.select_related("endpoint").get(pk=delivery_id)
    except WebhookDelivery.DoesNotExist:
        logger.error(f"WebhookDelivery with ID {delivery_id} does not exist.")
        return False

    endpoint = delivery.endpoint
    if not endpoint or not endpoint.is_active:
        logger.warning(f"Skipping delivery {delivery_id}: endpoint is inactive or missing.")
        return False

    # Serialize payload data consistently
    payload_data = delivery.payload
    body = json.dumps(payload_data, separators=(",", ":")).encode("utf-8")

    # Retrieve decrypted active secret using the model property
    secret_key = endpoint.secret
    if not secret_key:
        logger.error(f"Webhook endpoint {endpoint.id} has no valid secret configured.")
        return False

    # Compute HMAC SHA256 signature hex digest
    signature = hmac.new(
        secret_key.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Atelier-Signature": f"sha256={signature}",
    }

    try:
        response = requests.post(
            endpoint.target_url,
            data=body,
            headers=headers,
            timeout=10,
        )
        
        # Update delivery status based on response
        delivery.status_code = response.status_code
        delivery.response_body = response.text[:2000] # Truncate log if needed
        
        if 200 <= response.status_code < 300:
            delivery.status = "success"
            logger.info(f"Successfully delivered webhook {delivery.id} to {endpoint.target_url}")
        else:
            delivery.status = "failed"
            logger.warning(f"Webhook {delivery.id} failed with status {response.status_code}")
            
        delivery.save()
        return response.status_code
        
    except requests.RequestException as e:
        logger.error(f"Network error during delivery of webhook {delivery.id}: {e}")
        delivery.status = "failed"
        delivery.response_body = str(e)
        delivery.save()
        return None
