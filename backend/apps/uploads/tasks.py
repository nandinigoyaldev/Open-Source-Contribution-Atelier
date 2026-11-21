# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false
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
from .scanner import ScannerUnavailable, ScanTimeout, scan_file

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


def scan_upload(
    upload_id: str,
    attempt: int = 1,
    max_retries: int = 3,
) -> None:
    """Django-Q task: scan a quarantined file and publish or retain in quarantine."""

    with transaction.atomic():
        try:
            upload = UploadSession.objects.select_for_update().get(session_id=upload_id)
        except UploadSession.DoesNotExist:
            logger.warning("UploadSession %s not found for scan.", upload_id)
            return

        if upload.status not in {
            UploadSession.Status.QUARANTINED,
            UploadSession.Status.SCANNING,
        }:
            logger.info(
                "UploadSession %s is in status %s, skipping scan.",
                upload_id,
                upload.status,
            )
            return

        upload.status = UploadSession.Status.SCANNING
        upload.scan_started_at = timezone.now()
        upload.scan_message = (
            f"File is being scanned (attempt {attempt}/{max_retries})..."
        )
        upload.save(
            update_fields=["status", "scan_started_at", "scan_message", "updated_at"]
        )

    try:
        result = scan_file(upload.quarantine_path)
    except (ScannerUnavailable, ScanTimeout) as exc:
        is_timeout = isinstance(exc, ScanTimeout)
        result_type = (
            UploadScanHistory.Result.TIMEOUT
            if hasattr(UploadScanHistory.Result, "TIMEOUT")
            else UploadScanHistory.Result.ERROR
        )
        error_label = "timeout" if is_timeout else "unavailable"
        logger.warning(
            "Upload %s scan attempt %d failed (%s): %s",
            upload_id,
            attempt,
            error_label,
            exc,
        )

        with transaction.atomic():
            upload.refresh_from_db()
            UploadScanHistory.objects.create(
                upload=upload,
                result=result_type,
                message=f"Attempt {attempt}/{max_retries} failed ({error_label}): {exc}",
            )

            if attempt < max_retries:
                upload.status = UploadSession.Status.QUARANTINED
                upload.scan_message = (
                    f"Security scanner {error_label}. "
                    f"Retry {attempt + 1}/{max_retries} scheduled."
                )
                upload.save(update_fields=["status", "scan_message", "updated_at"])
                enqueue_upload_scan(
                    str(upload.session_id),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=2**attempt,
                )
                _notify(
                    upload,
                    "Upload scan delayed",
                    upload.scan_message,
                )
                return

            fail_closed = bool(getattr(settings, "UPLOAD_SCAN_FAIL_CLOSED", True))
            upload.scan_completed_at = timezone.now()
            if fail_closed:
                failed_status = getattr(
                    UploadSession.Status, "SCAN_FAILED", UploadSession.Status.FAILED
                )
                upload.status = failed_status
                upload.scan_message = (
                    f"Security scanner {error_label} after {max_retries} attempts. "
                    "File remains quarantined pending operator review."
                )
                upload.save(
                    update_fields=[
                        "status",
                        "scan_completed_at",
                        "scan_message",
                        "updated_at",
                    ]
                )
                _notify(upload, "Upload scan failed", upload.scan_message)
            else:
                _publish_clean_file(upload)
                upload.status = UploadSession.Status.CLEAN
                upload.scan_message = (
                    "Scanner unavailable; file released by configured fail-open policy."
                )
                upload.save(
                    update_fields=[
                        "status",
                        "file_path",
                        "quarantine_path",
                        "scan_completed_at",
                        "scan_message",
                        "updated_at",
                    ]
                )
                _notify(upload, "Upload ready", f"{upload.filename} is now available.")
            return

    except Exception as exc:
        logger.exception("Unexpected upload scan failure for %s: %s", upload_id, exc)
        with transaction.atomic():
            upload.refresh_from_db()
            failed_status = getattr(
                UploadSession.Status, "SCAN_FAILED", UploadSession.Status.FAILED
            )
            upload.status = failed_status
            upload.scan_completed_at = timezone.now()
            upload.scan_message = "Unexpected scanning error. File remains quarantined."
            upload.save(
                update_fields=[
                    "status",
                    "scan_completed_at",
                    "scan_message",
                    "updated_at",
                ]
            )
            UploadScanHistory.objects.create(
                upload=upload,
                result=UploadScanHistory.Result.ERROR,
                message=str(exc),
            )
            _notify(upload, "Upload scan error", upload.scan_message)
            return

    with transaction.atomic():
        upload.refresh_from_db()
        upload.scan_completed_at = timezone.now()

        if result.infected:
            # Retain infected files in quarantine only; never publish to media/uploads
            upload.status = UploadSession.Status.INFECTED
            upload.file_path = ""
            upload.scan_message = (
                f"Malware detected ({result.signature or 'threat signature'}). "
                "File remains in quarantine."
            )
            upload.save(
                update_fields=[
                    "status",
                    "file_path",
                    "scan_completed_at",
                    "scan_message",
                    "updated_at",
                ]
            )
            UploadScanHistory.objects.create(
                upload=upload,
                result=UploadScanHistory.Result.INFECTED,
                signature=result.signature or "detected_threat",
                message=upload.scan_message,
            )
            _notify(upload, "Upload blocked", upload.scan_message)
            return

        _publish_clean_file(upload)
        upload.status = UploadSession.Status.CLEAN
        upload.scan_message = "Scan complete. File is safe and available."
        upload.save(
            update_fields=[
                "status",
                "file_path",
                "quarantine_path",
                "scan_completed_at",
                "scan_message",
                "updated_at",
            ]
        )
        UploadScanHistory.objects.create(
            upload=upload,
            result=UploadScanHistory.Result.CLEAN,
            message=upload.scan_message,
        )
        _notify(upload, "Upload ready", f"{upload.filename} passed security scanning.")


def enqueue_upload_scan(
    upload_id: str,
    attempt: int = 1,
    max_retries: int = 3,
    delay_seconds: int = 0,
) -> None:
    """Queue scanning through the project's active Django-Q worker."""

    from django_q.tasks import async_task

    q_options = {}
    if delay_seconds > 0:
        q_options["delay"] = delay_seconds

    async_task(
        "apps.uploads.tasks.scan_upload",
        str(upload_id),
        attempt=attempt,
        max_retries=max_retries,
        q_options=q_options if q_options else None,
    )
