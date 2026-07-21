from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    """
    Append-only audit event for every domain write.

    Records are immutable at the Python layer: save() raises on existing PKs
    and delete() is unconditionally blocked. DB-level enforcement (restricted
    INSERT/SELECT-only user for the audit table) is an ops-side concern
    documented in TROUBLESHOOTING.md.
    """

    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_DELETED = "deleted"
    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_DELETED, "Deleted"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who triggered the change.",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.CharField(max_length=64, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.resource_type}#{self.resource_id} at {self.created_at}"

    # ── Immutability enforcement ───────────────────────────────────────────────

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError(
                "AuditEvent records are immutable and cannot be updated."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise PermissionError("AuditEvent records are immutable and cannot be deleted.")
