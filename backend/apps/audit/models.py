from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.audit.chain import AUDIT_CHAIN, ChainedModel


class AuditEvent(ChainedModel):
    """
    Append-only audit event for every domain write.

    Records are immutable at the Python layer: save() raises on existing PKs,
    delete() is unconditionally blocked and QuerySet.update() may only detach the
    actor (all from ChainedModel). Every new row, bulk_create included, is sealed
    into a hash chain so changes made straight in the database can be detected
    with ``manage.py verify_audit_chain``. DB-level enforcement (restricted
    INSERT/SELECT-only user for the audit table) is an ops-side concern
    documented in TROUBLESHOOTING.md.
    """

    chain = AUDIT_CHAIN

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
    # Copy of actor_id taken when the row is written. It is hashed and it stays
    # when the account is deleted and actor becomes NULL.
    actor_ref = models.BigIntegerField(null=True, editable=False)
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

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.resource_type}#{self.resource_id} at {self.created_at}"


class RBAC(AuditEvent):
    """
    Proxy model to provide a dedicated /admin/audit/rbac/ view for RBAC changes.
    """

    class Meta:
        proxy = True
        verbose_name = "RBAC Audit Event"
        verbose_name_plural = "RBAC Audit Events"


class AuditChainHead(models.Model):
    """The end of one hash chain. Writers lock this row to take turns."""

    chain = models.CharField(max_length=32, primary_key=True)
    last_sequence = models.PositiveBigIntegerField()
    head_hash = models.CharField(max_length=64)
    signature = models.CharField(max_length=64, blank=True)

    def __str__(self) -> str:
        return f"{self.chain} chain at {self.last_sequence}"


class AuditChainAnchor(models.Model):
    """
    Stands in for a run of rows removed by retention: the hash the run started
    from and the hash it ended on, signed by the application.
    """

    chain = models.CharField(max_length=32)
    first_sequence = models.PositiveBigIntegerField()
    last_sequence = models.PositiveBigIntegerField()
    previous_hash = models.CharField(max_length=64)
    last_hash = models.CharField(max_length=64)
    signature = models.CharField(max_length=64)
    archive_file = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["chain", "first_sequence"],
                name="audit_anchor_chain_first_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.chain} {self.first_sequence}-{self.last_sequence}"
