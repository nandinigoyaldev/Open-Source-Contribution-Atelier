import os
import uuid

from django.conf import settings

from django.db import models


class UploadSession(models.Model):
    class UploadType(models.TextChoices):
        AVATAR = "avatar", "Avatar"
        PROJECT = "project", "Project file"
        LESSON = "lesson", "Lesson asset"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPLOADING = "uploading", "Uploading"
        QUARANTINED = "quarantined", "Quarantined"
        SCANNING = "scanning", "Scanning"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        REJECTED = "rejected", "Rejected"
        RELEASED = "released", "Released by administrator"
        FAILED = "failed", "Failed"

    objects = models.Manager()
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="upload_sessions",
    )
    filename = models.CharField(max_length=255)
    upload_type = models.CharField(
        max_length=20, choices=UploadType.choices, default=UploadType.PROJECT
    )
    detected_mime_type = models.CharField(max_length=100, blank=True)
    total_size = models.BigIntegerField()
    total_chunks = models.PositiveIntegerField()
    uploaded_chunks = models.JSONField(default=list)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    file_path = models.CharField(max_length=512, blank=True)
    quarantine_path = models.CharField(max_length=512, blank=True)
    scan_message = models.CharField(max_length=500, blank=True)
    scan_started_at = models.DateTimeField(null=True, blank=True)
    scan_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_temp_dir(self):
        temp_dir = os.path.join(
            settings.MEDIA_ROOT, "temp_uploads", str(self.session_id)
        )
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    @property
    def is_accessible(self):
        return self.status in {self.Status.CLEAN, self.Status.RELEASED} and bool(
            self.file_path
        )

    def __str__(self):
        return f"{self.filename} ({self.status})"


class UploadScanHistory(models.Model):
    class Result(models.TextChoices):
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        ERROR = "error", "Scanner error"
        RELEASED = "released", "Released by administrator"

    upload = models.ForeignKey(
        UploadSession, on_delete=models.CASCADE, related_name="scan_history"
    )
    result = models.CharField(max_length=20, choices=Result.choices)
    engine = models.CharField(max_length=100, default="ClamAV")
    signature = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-scanned_at"]

    def __str__(self):
        return f"{self.upload_id}: {self.result}"
