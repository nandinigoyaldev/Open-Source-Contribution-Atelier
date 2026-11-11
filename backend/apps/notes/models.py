from django.conf import settings
from django.db import models


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes"
    )
    title = models.CharField(max_length=255, blank=True)
    encrypted_content = models.TextField()
    iv = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    client_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Note by {self.user.username} at {self.created_at}"
