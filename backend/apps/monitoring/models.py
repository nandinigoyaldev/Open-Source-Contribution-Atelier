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


class TaskRun(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("STARTED", "Started"),
        ("SUCCESS", "Success"),
        ("FAILURE", "Failure"),
        ("RETRY", "Retry"),
    ]

    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=255, db_index=True)
    correlation_id = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING", db_index=True
    )
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Duration in seconds")
    error_message = models.TextField(blank=True, default="")
    args_summary = models.TextField(blank=True, default="")
    retry_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Task Run"
        verbose_name_plural = "Task Runs"

    def __str__(self):
        return f"{self.task_name} [{self.task_id[:8]}] - {self.status}"
