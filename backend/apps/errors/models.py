from django.db import models
from django.utils import timezone

class ErrorGroup(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]

    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    message = models.TextField()
    module = models.CharField(max_length=255, db_index=True)
    count = models.PositiveIntegerField(default=0)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    resolved_at = models.DateTimeField(null=True, blank=True)
    cooldown_days = models.PositiveIntegerField(default=7)

    def __str__(self):
        return f"{self.module}: {self.message[:60]}"

class ErrorEvent(models.Model):
    group = models.ForeignKey(ErrorGroup, on_delete=models.CASCADE, related_name="events")
    raw_message = models.TextField()
    stacktrace = models.TextField(blank=True)
    request_id = models.CharField(max_length=100, null=True, blank=True)
    user_id = models.CharField(max_length=100, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Event for {self.group.id} at {self.timestamp}"
