from django.db import models
from django.utils import timezone


class BackupVerification(models.Model):
    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    backup_timestamp = models.DateTimeField()
    verification_timestamp = models.DateTimeField(default=timezone.now)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    logs = models.TextField(blank=True)

    class Meta:
        ordering = ["-verification_timestamp"]
        verbose_name_plural = "Backup verifications"

    def __str__(self):
        return f"Backup {self.backup_timestamp} - {self.status}"
