"""
Core scheduled tasks (distributed locking + database backups).
"""

import logging
import os
import subprocess
import time
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.models import SoftDeleteModel, PurgeLog
from .locks import distributed_lock, TaskLockManager

logger = logging.getLogger(__name__)


@shared_task
@distributed_lock("certificate_generation:{user_id}", timeout=120, retry_count=5)
def generate_certificate_task(user_id: int):
    """Generate certificate with distributed lock."""
    from apps.progress.models import Certificate
    from django.contrib.auth.models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return

    if Certificate.objects.filter(user=user).exists():
        logger.info(f"Certificate already exists for user {user_id}")
        return

    certificate = Certificate.objects.create(
        user=user,
        course_name="Open Source Contribution Course",
        issued_date=timezone.now()
    )

    logger.info(f"Certificate generated for user {user_id}: {certificate.verification_hash}")
    return {"certificate_id": certificate.id, "hash": certificate.verification_hash}


@shared_task
@distributed_lock("daily_digest:{user_id}", timeout=180, retry_count=3)
def send_daily_digest_task(user_id: int):
    """Send daily digest with distributed lock."""
    from django.contrib.auth.models import User
    from apps.progress.models import LessonProgress

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return

    progress = LessonProgress.objects.filter(
        user=user,
        completed=True,
        updated_at__gte=timezone.now() - timedelta(days=1)
    )

    if not progress.exists():
        logger.info(f"No new progress for user {user_id}")
        return

    context = {
        "user": user,
        "progress": progress,
        "completed_count": progress.count(),
        "date": timezone.now().date(),
    }

    html_content = render_to_string("notifications/daily_digest.html", context)
    plain_content = render_to_string("notifications/daily_digest.txt", context)

    send_mail(
        subject=f"Your Daily Progress Digest - {timezone.now().date()}",
        message=plain_content,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        recipient_list=[user.email],
        html_message=html_content,
        fail_silently=False,
    )

    logger.info(f"Daily digest sent to user {user_id}")
    return {"user_id": user_id, "completed_count": progress.count()}


@shared_task
@distributed_lock("leaderboard_recalculation", timeout=300, retry_count=3)
def recalculate_leaderboard_task():
    """Recalculate leaderboard with distributed lock."""
    from apps.dashboard.models import Leaderboard
    from apps.progress.models import LessonProgress
    from django.contrib.auth.models import User
    from django.db.models import Sum, Count

    logger.info("Starting leaderboard recalculation")

    user_scores = LessonProgress.objects.values('user').annotate(
        total_score=Sum('score'),
        completed_lessons=Count('id')
    ).order_by('-total_score')

    for user_data in user_scores:
        try:
            user = User.objects.get(id=user_data['user'])
            Leaderboard.objects.update_or_create(
                user=user,
                defaults={
                    'points': user_data['total_score'] or 0,
                    'completed_lessons': user_data['completed_lessons'] or 0,
                    'updated_at': timezone.now(),
                }
            )
        except User.DoesNotExist:
            continue

    top_users = Leaderboard.objects.select_related('user').order_by('-points')[:100]
    logger.info(f"Leaderboard recalculated with {len(top_users)} top users")
    return {"total_users": len(user_scores), "top_users": len(top_users)}


@shared_task
@distributed_lock("badge_evaluation:{user_id}", timeout=60, retry_count=5)
def evaluate_badges_task(user_id: int):
    """Evaluate badges with distributed lock."""
    from apps.progress.badge_evaluator import BadgeEvaluator
    from django.contrib.auth.models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return

    result = BadgeEvaluator.evaluate(user)
    logger.info(f"Badge evaluation completed for user {user_id}")
    return {"user_id": user_id, "badges_awarded": result.get("badges_awarded", [])}


@shared_task
@distributed_lock("notification_cleanup", timeout=120, retry_count=2)
def cleanup_notifications_task():
    """Clean up old notifications with distributed lock."""
    from apps.notifications.models import Notification

    cutoff = timezone.now() - timezone.timedelta(days=30)
    deleted_count, _ = Notification.objects.filter(
        status=Notification.STATUS_READ,
        created_at__lt=cutoff
    ).delete()

    logger.info(f"Cleaned up {deleted_count} old notifications")
    return {"deleted_count": deleted_count}

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


def archive_audit_logs():
    from apps.core.models import AdminAuditLog
    from django.conf import settings
    from django.utils import timezone
    import os
    import json
    from pathlib import Path

    retention_days = 90
    cutoff = timezone.now() - timezone.timedelta(days=retention_days)
    old_logs = AdminAuditLog.objects.filter(timestamp__lt=cutoff)
    count = old_logs.count()

    if count == 0:
        return 0

    audit_backup_dir = Path(settings.BACKUP_DIR) / "audit_logs"
    audit_backup_dir.mkdir(parents=True, exist_ok=True)

    filename = audit_backup_dir / f"audit_archive_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"

    logs_data = []
    for log in old_logs:
        logs_data.append({
            "id": log.id,
            "actor": log.actor.username if log.actor else None,
            "action": log.action,
            "target_type": str(log.target_type) if log.target_type else None,
            "target_id": log.target_id,
            "details": log.details,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address,
        })

    with open(filename, "w") as f:
        json.dump(logs_data, f, indent=2)

    old_logs.delete()
    logger.info(f"Archived {count} audit logs to {filename}")
    return count


# ──────────────────────────────────────────
# Database Backup Tasks
# ──────────────────────────────────────────

def backup_database():
    from django.conf import settings as _settings

    backup_dir = Path(getattr(_settings, "BACKUP_DIR", "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    db_settings = _settings.DATABASES.get("default", {})
    engine = db_settings.get("ENGINE", "")

    if "sqlite" in engine:
        output_path = backup_dir / f"backup_{timestamp}.json"
        _backup_sqlite(output_path)
    elif "postgresql" in engine or "postgis" in engine:
        output_path = backup_dir / f"backup_{timestamp}.sql"
        _backup_postgres(db_settings, output_path)
    else:
        logger.warning("backup_database: unsupported engine %s — skipping", engine)
        return None

    logger.info("Database backup created: %s", output_path)
    return str(output_path)


def _backup_sqlite(output_path: Path) -> None:
    import django
    from django.core.management import call_command
    import io

    buf = io.StringIO()
    call_command("dumpdata", stdout=buf, verbosity=0)
    output_path.write_text(buf.getvalue(), encoding="utf-8")


def _backup_postgres(db_settings: dict, output_path: Path) -> None:
    env = os.environ.copy()
    if db_settings.get("PASSWORD"):
        env["PGPASSWORD"] = db_settings["PASSWORD"]

    cmd = [
        "pg_dump",
        "--host", db_settings.get("HOST", "localhost"),
        "--port", str(db_settings.get("PORT") or 5432),
        "--username", db_settings.get("USER", ""),
        "--dbname", db_settings.get("NAME", ""),
        "--no-password",
        "--file", str(output_path),
    ]
    subprocess.run(cmd, env=env, check=True, capture_output=True)


def prune_old_backups():
    from django.conf import settings as _settings

    backup_dir = Path(getattr(_settings, "BACKUP_DIR", "backups"))
    retention_days = int(getattr(_settings, "BACKUP_RETENTION_DAYS", 30))
    cutoff = timezone.now() - timedelta(days=retention_days)

    if not backup_dir.exists():
        return 0

    deleted = 0
    for pattern in ("backup_*.json", "backup_*.sql"):
        for f in backup_dir.glob(pattern):
            mtime = timezone.datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
                logger.info("Pruned old backup: %s", f)

    logger.info("Backup pruning complete: %d file(s) removed", deleted)
    return deleted


@shared_task
def invalidate_tag_task(tag: str):
    """
    Asynchronously invalidate cached items tagged with a specific tag (or wildcard pattern).
    """
    from apps.core.cache.invalidation import invalidate_tag
    invalidate_tag(tag)

