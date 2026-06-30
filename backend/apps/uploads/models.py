from django.db import models
from django.contrib.auth.models import User
import uuid
import os
from django.conf import settings

class UploadSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPLOADING = "uploading", "Uploading"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    objects = models.Manager()
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="upload_sessions")
    filename = models.CharField(max_length=255)
    total_size = models.BigIntegerField()
    total_chunks = models.PositiveIntegerField()
    uploaded_chunks = models.JSONField(default=list) # Store list of successfully uploaded chunk indices
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    file_path = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_temp_dir(self):
        # Using a centralized temp directory for uploads
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads', str(self.session_id))
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    def __str__(self):
        return f"{self.filename} ({self.status})"
