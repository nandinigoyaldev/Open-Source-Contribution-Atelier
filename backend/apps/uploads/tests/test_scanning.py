from pathlib import Path
from unittest.mock import patch

import pytest

from apps.uploads.models import UploadSession
from apps.uploads.scanner import ScanResult
from apps.uploads.tasks import scan_upload


@pytest.mark.django_db
def test_clean_file_is_published(settings, django_user_model, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    user = django_user_model.objects.create_user(username="clean-user")
    quarantined = tmp_path / "quarantine" / "clean.txt"
    quarantined.parent.mkdir()
    quarantined.write_text("clean")
    upload = UploadSession.objects.create(
        user=user,
        filename="clean.txt",
        total_size=5,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantined),
    )

    with patch("apps.uploads.tasks.scan_file", return_value=ScanResult(infected=False)):
        scan_upload(str(upload.session_id))

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.CLEAN
    assert upload.file_path
    assert (Path(settings.MEDIA_ROOT) / upload.file_path).exists()


@pytest.mark.django_db
def test_eicar_detection_deletes_quarantined_file(settings, django_user_model, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    user = django_user_model.objects.create_user(username="infected-user")
    quarantined = tmp_path / "quarantine" / "eicar.txt"
    quarantined.parent.mkdir()
    quarantined.write_text("EICAR")
    upload = UploadSession.objects.create(
        user=user,
        filename="eicar.txt",
        total_size=5,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantined),
    )

    with patch("apps.uploads.tasks.scan_file", return_value=ScanResult(infected=True, signature="Eicar-Signature")):
        scan_upload(str(upload.session_id))

    upload.refresh_from_db()
    assert upload.status == UploadSession.Status.INFECTED
    assert not quarantined.exists()
    assert upload.scan_history.filter(signature="Eicar-Signature").exists()
