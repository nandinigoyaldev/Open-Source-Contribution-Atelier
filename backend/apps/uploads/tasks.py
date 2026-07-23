from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification

from .models import UploadScanHistory, UploadSession
from .scanner import ScannerUnavailable, scan_file

logger = logging.getLogger(__name__)


def _notify(upload: UploadSession, title: str, message: str) -> None:
    Notification.objects.create(
        recipient=upload.user,
        notif_type="achievement",
        title=title,
        message=message,
        meta={"upload_id": str(upload.session_id), "upload_status": upload.status},
    )


def _publish_clean_file(upload: UploadSession) -> None:
    source = Path(upload.quarantine_path)
    final_dir = Path(settings.MEDIA_ROOT) / "uploads"
    final_dir.mkdir(parents=True, exist_ok=True)
    destination = final_dir / f"{upload.session_id}_{Path(upload.filename).name}"
    shutil.move(str(source), destination)
    upload.file_path = str(destination.relative_to(settings.MEDIA_ROOT)).replace(
        "\\", "/"
    )
    upload.quarantine_path = ""


def scan_upload(upload_id: str) -> None:
    """Django-Q task: scan a quarantined file and publish or delete it."""

    with transaction.atomic():
        upload = UploadSession.objects.select_for_update().get(session_id=upload_id)
        if upload.status not in {
            UploadSession.Status.QUARANTINED,
            UploadSession.Status.SCANNING,
        }:
            return
        upload.status = UploadSession.Status.SCANNING
        upload.scan_started_at = timezone.now()
        upload.scan_message = "File is being scanned..."
        upload.save(
            update_fields=["status", "scan_started_at", "scan_message", "updated_at"]
        )

    try:
        result = scan_file(upload.quarantine_path)
    except ScannerUnavailable as exc:
        fail_closed = bool(getattr(settings, "UPLOAD_SCAN_FAIL_CLOSED", True))
        upload.refresh_from_db()
        UploadScanHistory.objects.create(
            upload=upload,
            result=UploadScanHistory.Result.ERROR,
            message=str(exc),
        )
        upload.scan_completed_at = timezone.now()
        if fail_closed:
            upload.status = UploadSession.Status.FAILED
            upload.scan_message = (
                "Security scanner unavailable. File remains quarantined."
            )
            _notify(upload, "Upload scan delayed", upload.scan_message)
        else:
            _publish_clean_file(upload)
            upload.status = UploadSession.Status.CLEAN
            upload.scan_message = (
                "Scanner unavailable; file released by configured fail-open policy."
            )
            _notify(upload, "Upload ready", f"{upload.filename} is now available.")
        upload.save()
        return
    except Exception as exc:
        logger.exception("Unexpected upload scan failure for %s", upload_id)
        upload.refresh_from_db()
        upload.status = UploadSession.Status.FAILED
        upload.scan_completed_at = timezone.now()
        upload.scan_message = "Unexpected scanning error. File remains quarantined."
        upload.save()
        UploadScanHistory.objects.create(
            upload=upload,
            result=UploadScanHistory.Result.ERROR,
            message=str(exc),
        )
        return

    upload.refresh_from_db()
    upload.scan_completed_at = timezone.now()

    if result.infected:
        if upload.quarantine_path and os.path.exists(upload.quarantine_path):
            os.remove(upload.quarantine_path)
        upload.status = UploadSession.Status.INFECTED
        upload.quarantine_path = ""
        upload.scan_message = "Malware detected. The uploaded file was deleted."
        UploadScanHistory.objects.create(
            upload=upload,
            result=UploadScanHistory.Result.INFECTED,
            signature=result.signature,
            message=upload.scan_message,
        )
        upload.save()
        _notify(upload, "Upload blocked", upload.scan_message)
        return

    _publish_clean_file(upload)
    upload.status = UploadSession.Status.CLEAN
    upload.scan_message = "Scan complete. File is safe and available."
    UploadScanHistory.objects.create(
        upload=upload,
        result=UploadScanHistory.Result.CLEAN,
        message=upload.scan_message,
    )
    upload.save()
    _notify(upload, "Upload ready", f"{upload.filename} passed security scanning.")


def enqueue_upload_scan(upload_id: str) -> None:
    """Queue scanning through the project's active Django-Q worker."""

    from django_q.tasks import async_task

    async_task("apps.uploads.tasks.scan_upload", str(upload_id))
