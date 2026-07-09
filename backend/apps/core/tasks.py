import time
import logging
from datetime import timedelta
from django.utils import timezone
from django.apps import apps
from apps.core.models import SoftDeleteModel, PurgeLog

logger = logging.getLogger(__name__)


def purge_expired_soft_deleted_records(retention_days=30, batch_size=1000):
    """
    Automated GDPR data purge pipeline.
    Identifies all models inheriting from SoftDeleteModel and permanently deletes
    records that have been soft-deleted for longer than `retention_days`.
    Runs in batches to prevent database locks.
    """
    threshold_date = timezone.now() - timedelta(days=retention_days)
    logger.info(f"Starting GDPR data purge for records deleted before {threshold_date}")

    for model in apps.get_models():
        if issubclass(model, SoftDeleteModel) and model is not SoftDeleteModel:
            _purge_for_model(model, threshold_date, batch_size)


def _purge_for_model(model, threshold_date, batch_size):
    start_time = time.time()

    # Query all expired records
    # Note: we must use all_objects or deleted_objects because objects filters out deleted rows
    qs = model.deleted_objects.filter(deleted_at__lt=threshold_date)
    total_to_delete = qs.count()

    if total_to_delete == 0:
        return

    logger.info(
        f"Found {total_to_delete} expired records for {model.__name__}. Beginning purge."
    )
    deleted_count = 0

    # Delete in batches to avoid locking huge tables
    # Since we are deleting, we can just repeatedly delete the first `batch_size` items
    while True:
        # We fetch IDs first so we can pass them to filter(...).delete()
        batch_ids = list(qs.values_list("pk", flat=True)[:batch_size])
        if not batch_ids:
            break

        # Hard delete this batch
        # Standard .delete() on QuerySet natively respects our overridden hard_delete
        # Actually, QuerySet.delete() maps to SQL DELETE natively, so it bypasses our model's delete()
        # Wait, if we overrode SoftDeleteQuerySet.delete, it does an update!
        # We need to call the actual SQL delete. Our SoftDeleteQuerySet has a `hard_delete` method.
        deleted, _ = model.deleted_objects.filter(pk__in=batch_ids).hard_delete()
        deleted_count += deleted

    duration = time.time() - start_time
    logger.info(
        f"Successfully purged {deleted_count} records from {model.__name__} in {duration:.2f}s"
    )

    # Create Audit Log
    PurgeLog.objects.create(
        model_name=model.__name__,
        records_deleted=deleted_count,
        duration_seconds=duration,
    )
