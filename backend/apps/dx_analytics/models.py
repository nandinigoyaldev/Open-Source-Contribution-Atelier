import uuid
from django.db import models
from django.contrib.auth.models import User


class DeveloperExperienceMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    workflow_name = models.CharField(max_length=100)
    execution_time_ms = models.IntegerField()
    success = models.BooleanField(default=True)
    failure_reason = models.TextField(null=True, blank=True)
    developer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    commit_hash = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.workflow_name} - {'Success' if self.success else 'Failure'}"


class DXSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    dx_score = models.FloatField()
    anomaly_score = models.FloatField(default=0.0)
    total_failures = models.IntegerField(default=0)
    avg_duration = models.FloatField(default=0.0)
    is_anomaly = models.BooleanField(default=False)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"DX Snapshot {self.timestamp} - Score: {self.dx_score}"
