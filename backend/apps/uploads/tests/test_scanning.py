from apps.uploads.scanner import ScannerUnavailable

@pytest.mark.django_db
def test_scanner_unavailable_handles_gracefully(settings, django_user_model, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    user = django_user_model.objects.create_user(username="error-user")
    quarantined = tmp_path / "quarantine" / "error.txt"
    quarantined.parent.mkdir()
    quarantined.write_text("test")
    upload = UploadSession.objects.create(
        user=user,
        filename="error.txt",
        total_size=4,
        total_chunks=1,
        status=UploadSession.Status.QUARANTINED,
        quarantine_path=str(quarantined),
    )

    with patch("apps.uploads.tasks.scan_file", side_effect=ScannerUnavailable("ClamAV unavailable")):
        with pytest.raises(ScannerUnavailable):
            scan_upload(str(upload.session_id))

    upload.refresh_from_db()
    # Ensure session remains safely quarantined or handles the failure state appropriately
    assert upload.status == UploadSession.Status.QUARANTINED
