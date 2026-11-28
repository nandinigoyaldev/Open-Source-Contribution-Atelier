import json
import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import requests
from celery import shared_task
from django.conf import settings
from django.db import router, transaction
from django.utils import timezone

from apps.audit.chain import anchor_pruned_rows, row_problems, verify_chain
from apps.audit.models import AuditEvent

logger = logging.getLogger(__name__)

_CHECKPOINT_TIMEOUT_SECONDS = 10

# SQLite limits how many parameters one query may carry.
_DELETE_BATCH_SIZE = 500


@shared_task
def archive_audit_events():
    """
    Archive audit events older than the configured TTL (default 90 days)
    to a JSON file in the configured storage directory, then delete them from the database.
    """
    retention_days = getattr(settings, "AUDIT_RETENTION_DAYS", 90)
    cutoff = timezone.now() - timedelta(days=retention_days)

    events_to_archive = AuditEvent.objects.filter(created_at__lt=cutoff)
    count = events_to_archive.count()

    if count == 0:
        logger.info("No audit events to archive.")
        return 0

    archive_dir = Path(
        getattr(settings, "AUDIT_ARCHIVE_DIR", settings.BASE_DIR / "archives" / "audit")
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    # Anchors point at this file, so two runs must never share a name.
    archive_file = archive_dir / f"audit_archive_{timestamp}_{uuid.uuid4().hex}.json"

    # Batch serialize and write to JSON
    using = router.db_for_write(AuditEvent)
    serialized_events = []
    links = []
    ids = []
    held_back = 0
    for event in events_to_archive.using(using).iterator():
        # A row that fails its own check is evidence. Pruning it would hide it
        # behind an anchor, so it stays for verify_audit_chain to report.
        if event.sequence is None or row_problems(AuditEvent.chain, event):
            held_back += 1
            continue
        ids.append(event.id)
        links.append((event.sequence, event.previous_hash, event.hash))
        serialized_events.append(
            {
                "id": event.id,
                "actor_id": event.actor_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "before": event.before,
                "after": event.after,
                "correlation_id": event.correlation_id,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "created_at": event.created_at.isoformat(),
                "extra": event.extra,
                "actor_ref": event.actor_ref,
                "sequence": event.sequence,
                "previous_hash": event.previous_hash,
                "hash": event.hash,
            }
        )

    if held_back:
        logger.error(
            "Kept %d old audit events that fail the hash chain check. "
            "Run verify_audit_chain.",
            held_back,
        )
    if not ids:
        return 0

    with open(archive_file, "x", encoding="utf-8") as f:
        json.dump(serialized_events, f, indent=2)

    logger.info("Archived %d audit events to %s", len(ids), archive_file)

    # Anchors and delete commit together, so the chain never has an unexplained
    # hole. QuerySet.delete() does not go through AuditEvent.delete(), which
    # always raises.
    deleted_count = 0
    # Typed as Any: without Django stubs, atomic(using=...) reads as a decorator.
    atomic: Any = transaction.atomic
    with atomic(using=using):
        anchor_pruned_rows(AuditEvent.chain, links, using, str(archive_file))
        for start in range(0, len(ids), _DELETE_BATCH_SIZE):
            batch = ids[start : start + _DELETE_BATCH_SIZE]
            deleted_count += (
                AuditEvent.objects.using(using).filter(pk__in=batch).delete()[0]
            )
        if deleted_count != len(ids):
            raise RuntimeError(
                "Audit events changed during archiving, nothing was deleted."
            )

    logger.info("Deleted %d archived audit events from database.", deleted_count)
    return deleted_count


@shared_task
def publish_audit_checkpoints():
    """
    Verify both hash chains and send their current heads outside the database:
    always to the log, and to AUDIT_CHECKPOINT_URL when it is set. Raises when
    a chain fails or the checkpoints cannot be delivered.
    """
    from apps.audit.management.commands.verify_audit_chain import CHAINED_MODELS

    checkpoints = []
    failed = []
    for name, model in sorted(CHAINED_MODELS.items()):
        report = verify_chain(model)
        if not report.ok:
            failed.append(name)
            logger.error(
                "Audit chain %s failed verification, no checkpoint published.", name
            )
        elif report.head_sequence:
            checkpoint = f"{name}:{report.head_sequence}:{report.head_hash}"
            checkpoints.append(checkpoint)
            logger.info("Audit chain checkpoint %s", checkpoint)

    url = getattr(settings, "AUDIT_CHECKPOINT_URL", "")
    if url and (checkpoints or failed):
        # The URL may carry a token, so it stays out of logs and tracebacks.
        try:
            response = requests.post(
                url,
                json={"checkpoints": checkpoints, "failed": failed},
                timeout=_CHECKPOINT_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            outcome = f"HTTP {response.status_code}"
            delivered = 200 <= response.status_code < 300
        except requests.RequestException as error:
            outcome = type(error).__name__
            delivered = False
        if not delivered:
            raise RuntimeError(f"Audit checkpoints were not delivered: {outcome}")

    if failed:
        raise RuntimeError(f"Audit chain verification failed: {', '.join(failed)}")
    return checkpoints
