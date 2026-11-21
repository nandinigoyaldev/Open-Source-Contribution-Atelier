import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.uploads.models import UploadScanHistory, UploadSession
from apps.uploads.scanner import ScannerUnavailable, ScanResult, ScanTimeout
from apps.uploads.tasks import scan_upload

User = get_user_model()


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        username="uploader-alice",
        email="alice@example.com",
        password="secure-password-123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="other-bob",
        email="bob@example.com",
        password="secure-password-123",
    )


@pytest.fixture
def client_uploader(uploader):
    client = APIClient()
    client.force_authenticate(user=uploader)
    return client


@pytest.fixture
def client_other(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


@pytest.mark.django_db
def test_new_upload_begins_quarantined_and_download_blocked(
    client_uploader, uploader, tmp_path, settings
):
    """AC: New uploads are never publicly usable before a clean result."""
    settings.MEDIA_ROOT = tmp_path / "media"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "quarantined_file.txt"
    quarantine_file.write_text("sensitivedata")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="quarantined_file.txt",
        total_size=13,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantine_file),
    )

    download_url = reverse(
        "uploads:download_upload", kwargs={"session_id": upload.session_id}
    )
    status_url = reverse(
        "uploads:upload_status", kwargs={"session_id": upload.session_id}
    )

    # 1. Download must be blocked while quarantined
    res_download = client_uploader.get(download_url)
    assert res_download.status_code == 423
    assert res_download.data["status"] == UploadSession.Status.QUARANTINED
    assert "quarantine" in res_download.data["error"].lower()

    # 2. Status view must show is_accessible=False, file_path=None, download_url=None
    res_status = client_uploader.get(status_url)
    assert res_status.status_code == 200
    assert res_status.data["is_accessible"] is False
    assert res_status.data["is_clean"] is False
    assert res_status.data["file_path"] is None
    assert res_status.data["download_url"] is None


@pytest.mark.django_db
def test_download_guards_against_unauthorized_users(
    client_uploader, client_other, uploader, tmp_path, settings
):
    """Non-owners (non-staff) cannot access or download another user's upload."""
    settings.MEDIA_ROOT = tmp_path / "media"
    final_dir = tmp_path / "media" / "uploads"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_file = final_dir / "alice_file.txt"
    final_file.write_text("alice content")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="alice_file.txt",
        total_size=13,
        total_chunks=1,
        status=UploadSession.Status.CLEAN,
        file_path="uploads/alice_file.txt",
    )

    download_url = reverse(
        "uploads:download_upload", kwargs={"session_id": upload.session_id}
    )

    # Alice (owner) can download
    res_owner = client_uploader.get(download_url)
    assert res_owner.status_code == 200

    # Bob (non-owner) gets 404
    res_other = client_other.get(download_url)
    assert res_other.status_code == 404


@pytest.mark.django_db
def test_clean_scan_enables_download_with_content(
    client_uploader, uploader, tmp_path, settings
):
    """AC: When scan finishes clean, file is published and downloadable."""
    settings.MEDIA_ROOT = tmp_path / "media"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "clean_report.txt"
    quarantine_file.write_text("clean report payload")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="clean_report.txt",
        total_size=20,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantine_file),
    )

    with patch("apps.uploads.tasks.scan_file", return_value=ScanResult(infected=False)):
        scan_upload(str(upload.session_id))

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.CLEAN
    assert upload.is_accessible is True
    assert upload.file_path != ""
    assert not quarantine_file.exists()

    download_url = reverse(
        "uploads:download_upload", kwargs={"session_id": upload.session_id}
    )
    res_download = client_uploader.get(download_url)
    assert res_download.status_code == 200
    assert b"".join(res_download.streaming_content) == b"clean report payload"


@pytest.mark.django_db
def test_infected_upload_retains_quarantine_and_blocks_download(
    client_uploader, uploader, tmp_path, settings
):
    """AC: Infected files are retained ONLY in quarantine with signature recorded."""
    settings.MEDIA_ROOT = tmp_path / "media"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "trojan.bin"
    quarantine_file.write_bytes(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="trojan.bin",
        total_size=34,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantine_file),
    )

    with patch(
        "apps.uploads.tasks.scan_file",
        return_value=ScanResult(infected=True, signature="Win32.Trojan.Test"),
    ):
        scan_upload(str(upload.session_id))

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.INFECTED
    # File is retained strictly in quarantine
    assert quarantine_file.exists()
    assert upload.quarantine_path == str(quarantine_file)
    assert not upload.file_path
    assert upload.is_accessible is False

    # Signature recorded in history
    history = upload.scan_history.first()
    assert history is not None
    assert history.result == UploadScanHistory.Result.INFECTED
    assert history.signature == "Win32.Trojan.Test"

    # Download must be forbidden (HTTP 403)
    download_url = reverse(
        "uploads:download_upload", kwargs={"session_id": upload.session_id}
    )
    res = client_uploader.get(download_url)
    assert res.status_code == 403
    assert res.data["status"] == UploadSession.Status.INFECTED
    assert "infected" in res.data["error"].lower()


@pytest.mark.django_db
def test_scanner_timeout_retry_backoff_and_resumption(
    client_uploader, uploader, tmp_path, settings
):
    """AC: Timeout cases are retryable and observable."""
    settings.MEDIA_ROOT = tmp_path / "media"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "large_archive.zip"
    quarantine_file.write_bytes(b"PK\x03\x04archive")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="large_archive.zip",
        total_size=11,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantine_file),
    )

    # Attempt 1: times out
    with (
        patch(
            "apps.uploads.tasks.scan_file",
            side_effect=ScanTimeout("Scanner subprocess timed out"),
        ),
        patch("apps.uploads.tasks.enqueue_upload_scan") as mock_enqueue,
    ):
        scan_upload(str(upload.session_id), attempt=1, max_retries=3)

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.QUARANTINED
    assert "Retry 2/3 scheduled" in upload.scan_message
    mock_enqueue.assert_called_once_with(
        str(upload.session_id), attempt=2, max_retries=3, delay_seconds=2
    )

    # Check history records observable timeout
    history = upload.scan_history.first()
    assert history is not None
    assert history.result in {
        UploadScanHistory.Result.TIMEOUT,
        UploadScanHistory.Result.ERROR,
    }
    assert "timeout" in history.message.lower()

    # Attempt 2: succeeds on retry
    with patch("apps.uploads.tasks.scan_file", return_value=ScanResult(infected=False)):
        scan_upload(str(upload.session_id), attempt=2, max_retries=3)

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.CLEAN
    assert upload.is_accessible is True


@pytest.mark.django_db
def test_scanner_unavailable_exhausts_retries_and_fails_closed(
    client_uploader, uploader, tmp_path, settings
):
    """AC: Scanner-unavailable cases fail-closed after exhausting retries."""
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.UPLOAD_SCAN_FAIL_CLOSED = True
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "unscanned.txt"
    quarantine_file.write_text("unscanned")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="unscanned.txt",
        total_size=9,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantine_file),
    )

    with patch(
        "apps.uploads.tasks.scan_file",
        side_effect=ScannerUnavailable("ClamAV daemon offline"),
    ):
        scan_upload(str(upload.session_id), attempt=3, max_retries=3)

    upload.refresh_from_db()
    assert upload.status in {
        UploadSession.Status.FAILED,
        getattr(UploadSession.Status, "SCAN_FAILED", "scan_failed"),
    }
    assert quarantine_file.exists()
    assert not upload.file_path
    assert upload.is_accessible is False

    # Status check confirms retryable and observable
    status_url = reverse(
        "uploads:upload_status", kwargs={"session_id": upload.session_id}
    )
    res = client_uploader.get(status_url)
    assert res.status_code == 200
    assert res.data["retryable"] is True
    assert res.data["is_accessible"] is False


@pytest.mark.django_db
def test_manual_retry_endpoint(client_uploader, uploader, tmp_path, settings):
    """Operators/users can manually retry an upload whose scan failed."""
    settings.MEDIA_ROOT = tmp_path / "media"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "retry_me.txt"
    quarantine_file.write_text("retry payload")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="retry_me.txt",
        total_size=13,
        total_chunks=1,
        status=UploadSession.Status.FAILED,
        quarantine_path=str(quarantine_file),
    )

    retry_url = reverse("uploads:retry_scan", kwargs={"session_id": upload.session_id})

    with patch("apps.uploads.views.enqueue_upload_scan") as mock_enqueue:
        res = client_uploader.post(retry_url)

    assert res.status_code == 202
    mock_enqueue.assert_called_once_with(str(upload.session_id))
    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.QUARANTINED


@pytest.mark.django_db
def test_race_condition_concurrent_scans_and_downloads(
    client_uploader, uploader, tmp_path, settings
):
    """AC: Tests cover race conditions between upload, scan, and download."""
    settings.MEDIA_ROOT = tmp_path / "media"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / "race.txt"
    quarantine_file.write_text("concurrent content")

    upload = UploadSession.objects.create(
        user=uploader,
        filename="race.txt",
        total_size=18,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantine_file),
    )

    download_url = reverse(
        "uploads:download_upload", kwargs={"session_id": upload.session_id}
    )

    # 1. Download while in QUARANTINED returns 423
    assert client_uploader.get(download_url).status_code == 423

    # 2. Simulate worker 1 acquiring the lock and marking SCANNING
    with patch("apps.uploads.tasks.scan_file", return_value=ScanResult(infected=False)):
        scan_upload(str(upload.session_id))

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.CLEAN

    # 3. Subsequent scan trigger sees CLEAN status and safely exits without double-publishing
    with patch("apps.uploads.tasks.scan_file") as mock_scan:
        scan_upload(str(upload.session_id))
        mock_scan.assert_not_called()

    # 4. Immediate download succeeds
    res_after = client_uploader.get(download_url)
    assert res_after.status_code == 200
    assert b"".join(res_after.streaming_content) == b"concurrent content"
