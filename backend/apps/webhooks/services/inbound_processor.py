import json
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from django.utils import timezone

from apps.webhooks.models import InboundWebhookEvent

logger = logging.getLogger(__name__)


def process_inbound_webhook(
    provider: str,
    event_id: str,
    event_type: str,
    payload: Any,
    signature_valid: bool,
    event_timestamp=None,
    sequence: Optional[int] = None,
    out_of_order_policy: str = "reject",
    handler: Optional[Callable[[Any], None]] = None,
) -> Tuple[bool, str, InboundWebhookEvent]:
    """
    Safely process inbound webhook with replay protection, duplicate suppression,
    signature audit logging, and out-of-order policy enforcement.

    Returns (is_acknowledged: bool, outcome_reason: str, event_record: InboundWebhookEvent)
    """
    clean_payload = payload if isinstance(payload, (dict, list)) else {}

    # 1. Invalid signature check
    if not signature_valid:
        record = InboundWebhookEvent.objects.create(
            provider=provider,
            event_id=event_id or f"invalid_{timezone.now().timestamp()}",
            event_type=event_type,
            signature_valid=False,
            status="rejected",
            payload=clean_payload,
            event_timestamp=event_timestamp,
            failure_reason="Invalid webhook signature verification",
        )
        logger.warning(
            f"Inbound webhook signature rejected: provider={provider}, event_id={event_id}"
        )
        return False, "invalid_signature", record

    # 2. Duplicate event check (Replay Protection)
    if event_id:
        existing = InboundWebhookEvent.objects.filter(
            provider=provider, event_id=event_id
        ).first()
        if existing:
            logger.info(
                f"Duplicate inbound webhook event received: provider={provider}, event_id={event_id}. Acknowledging without side effects."
            )
            return True, "duplicate_acknowledged", existing

    # 3. Out-of-order check
    if event_timestamp:
        latest_event = (
            InboundWebhookEvent.objects.filter(
                provider=provider,
                event_type=event_type,
                status="processed",
                event_timestamp__isnull=False,
            )
            .order_by("-event_timestamp")
            .first()
        )

        if (
            latest_event
            and latest_event.event_timestamp
            and event_timestamp < latest_event.event_timestamp
        ):
            if out_of_order_policy == "reject":
                record = InboundWebhookEvent.objects.create(
                    provider=provider,
                    event_id=event_id,
                    event_type=event_type,
                    signature_valid=True,
                    status="out_of_order",
                    payload=clean_payload,
                    event_timestamp=event_timestamp,
                    sequence=sequence,
                    failure_reason=(
                        f"Out-of-order event: received timestamp {event_timestamp} is older than "
                        f"latest processed timestamp {latest_event.event_timestamp}"
                    ),
                )
                logger.warning(
                    f"Out-of-order webhook rejected: provider={provider}, event_id={event_id}"
                )
                return False, "out_of_order_rejected", record

    # 4. Process event and execute side effects
    record = InboundWebhookEvent.objects.create(
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        signature_valid=True,
        status="processed",
        payload=clean_payload,
        event_timestamp=event_timestamp,
        sequence=sequence,
    )

    if handler:
        try:
            handler(clean_payload)
        except Exception as exc:
            record.status = "failed"
            record.failure_reason = str(exc)
            record.save(update_fields=["status", "failure_reason"])
            logger.exception(
                f"Handler failed for inbound webhook: provider={provider}, event_id={event_id}"
            )
            return False, "handler_error", record

    return True, "processed", record
