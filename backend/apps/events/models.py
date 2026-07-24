"""
Domain Event models for event-driven architecture.
"""

import json
import uuid
from django.db import models
from django.conf import settings

from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

# ============================================================
# Event Models
# ============================================================


class DomainEvent(models.Model):
    """
    Base model for all domain events.
    """

    # Event statuses
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_RETRY = "retry"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_RETRY, "Retry"),
    ]

    # Priority levels
    PRIORITY_LOW = 0
    PRIORITY_NORMAL = 1
    PRIORITY_HIGH = 2
    PRIORITY_CRITICAL = 3

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_CRITICAL, "Critical"),
    ]

    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=100, db_index=True)
    event_name = models.CharField(max_length=100, db_index=True)
    version = models.IntegerField(default=1)

    # Event data
    data = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)

    # Actor (who triggered the event)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_events",
    )

    # Target (what the event is about)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")

    # Status and processing
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    # Timestamps
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Error tracking
    last_error = models.TextField(blank=True)
    error_stack = models.JSONField(default=list)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["event_type", "status"], name="idx_event_typestatus"),
            models.Index(fields=["event_name", "status"], name="idx_event_namestatus"),
            models.Index(
                fields=["occurred_at", "status"], name="idx_occurred_atstatus"
            ),
            models.Index(fields=["actor", "event_type"], name="idx_actorevent_type"),
        ]

    def __str__(self):
        return f"{self.event_name} ({self.id})"

    def mark_processing(self):
        """Mark event as being processed."""
        self.status = self.STATUS_PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_completed(self):
        """Mark event as completed."""
        self.status = self.STATUS_COMPLETED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at", "updated_at"])

    def mark_failed(self, error: str):
        """Mark event as failed."""
        self.status = self.STATUS_FAILED
        self.last_error = error
        self.error_stack.append(
            {
                "timestamp": timezone.now().isoformat(),
                "error": error,
                "retry_count": self.retry_count,
            }
        )
        self.save(update_fields=["status", "last_error", "error_stack", "updated_at"])

    def mark_retry(self):
        """Mark event for retry."""
        self.status = self.STATUS_RETRY
        self.retry_count += 1
        self.save(update_fields=["status", "retry_count", "updated_at"])

    def should_retry(self):
        """Check if event should be retried."""
        return self.retry_count < self.max_retries

    def to_dict(self):
        """Convert event to dictionary."""
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "event_name": self.event_name,
            "version": self.version,
            "data": self.data,
            "metadata": self.metadata,
            "actor_id": self.actor_id,
            "target": {
                "content_type": self.content_type_id,
                "object_id": self.object_id,
            },
            "status": self.status,
            "priority": self.priority,
            "occurred_at": self.occurred_at.isoformat(),
        }


class EventSubscription(models.Model):
    """
    Model for event subscriptions (who wants to handle which events).
    """

    subscriber = models.CharField(max_length=200)  # Handler class path
    event_types = models.JSONField(default=list)  # List of event types to handle
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)  # Higher = processed first
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-priority"]

    def __str__(self):
        return f"{self.subscriber} -> {', '.join(self.event_types)}"


class EventHandler(models.Model):
    """
    Model for tracking event handlers.
    """

    HANDLER_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("error", "Error"),
    ]

    name = models.CharField(max_length=200, unique=True)
    event_type = models.CharField(max_length=100)
    handler_class = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20, choices=HANDLER_STATUS_CHOICES, default="active"
    )
    last_run = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["event_type", "handler_class"]

    def __str__(self):
        return f"{self.name} ({self.event_type})"
