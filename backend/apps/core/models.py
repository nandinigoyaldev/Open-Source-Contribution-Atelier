from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class SoftDeleteQuerySet(models.QuerySet):
    """
    QuerySet that handles soft deletion.
    Calling .delete() updates `deleted_at` instead of removing from DB.
    """

    def delete(self, hard=False, deleted_by=None, deletion_reason=""):
        if hard:
            return super().delete()
        return super().update(
            deleted_at=timezone.now(),
            deleted_by=deleted_by,
            deletion_reason=deletion_reason,
        )

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return super().update(deleted_at=None, deleted_by=None, deletion_reason="")


class SoftDeleteManager(models.Manager):
    """
    Manager that filters out soft-deleted records by default.
    """

    def __init__(self, *args, **kwargs):
        self.with_deleted = kwargs.pop("with_deleted", False)
        self.only_deleted = kwargs.pop("only_deleted", False)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        qs = SoftDeleteQuerySet(self.model, using=self._db)
        if self.only_deleted:
            return qs.exclude(deleted_at__isnull=True)
        if not self.with_deleted:
            return qs.filter(deleted_at__isnull=True)
        return qs


class SoftDeleteModel(models.Model):
    """
    Abstract base class for models that should support soft deletion.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who soft-deleted this record.",
    )
    deletion_reason = models.TextField(blank=True, help_text="Reason for deletion")

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager(with_deleted=True)
    deleted_objects = SoftDeleteManager(only_deleted=True)

    class Meta:
        abstract = True

    def delete(
        self,
        using=None,
        keep_parents=False,
        hard=False,
        deleted_by=None,
        deletion_reason="",
        cascade=True,
    ):
        """
        Soft deletes the record. If `hard=True`, deletes permanently.
        If `cascade=True`, propagates soft delete to related `SoftDeleteModel` instances.
        """
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)

        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.deletion_reason = deletion_reason
        self.save(
            using=using, update_fields=["deleted_at", "deleted_by", "deletion_reason"]
        )

        if cascade:
            self._cascade_soft_delete(using, deleted_by, deletion_reason)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently deletes the record from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self, cascade=True):
        """Restores the soft-deleted record."""
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = ""
        self.save(update_fields=["deleted_at", "deleted_by", "deletion_reason"])

        if cascade:
            self._cascade_restore()

    def _cascade_soft_delete(self, using, deleted_by, deletion_reason):
        """Helper to soft-delete related models."""
        for rel in self._meta.related_objects:
            if not issubclass(rel.related_model, SoftDeleteModel):
                continue
            accessor = getattr(self, rel.get_accessor_name(), None)
            if accessor:
                if hasattr(accessor, "all"):
                    for obj in accessor.all():
                        obj.delete(
                            hard=False,
                            deleted_by=deleted_by,
                            deletion_reason=deletion_reason,
                            cascade=True,
                        )
                else:
                    accessor.delete(
                        hard=False,
                        deleted_by=deleted_by,
                        deletion_reason=deletion_reason,
                        cascade=True,
                    )

    def _cascade_restore(self):
        """Helper to restore related soft-deleted models."""
        for rel in self._meta.related_objects:
            if not issubclass(rel.related_model, SoftDeleteModel):
                continue
            # We must use all_objects because the default manager hides deleted objects
            accessor_name = rel.get_accessor_name()
            # It's tricky to query through the accessor if it hides deleted objects.
            # Instead, we construct a query on the related model's all_objects manager.
            related_model = rel.related_model
            field_name = rel.field.name

            # Find related objects that were deleted at or after this object's deletion time (approx)
            # Actually, standard cascade restore is simpler if we just restore all linked.
            related_qs = related_model.deleted_objects.filter(**{field_name: self.pk})
            for obj in related_qs:
                obj.restore(cascade=True)


class PurgeLog(models.Model):
    """
    Audit log for automated GDPR scheduled purge processes.
    """

    model_name = models.CharField(max_length=255)
    records_deleted = models.PositiveIntegerField()
    execution_time = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.FloatField(help_text="Time taken to execute the purge")

    def __str__(self):
        return f"Purged {self.records_deleted} from {self.model_name} at {self.execution_time}"


class AdminAuditLog(models.Model):
    """
    Audit log for tracking sensitive admin actions (e.g., user bans, deletions).
    """

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_audit_logs",
        help_text="The admin user who performed the action.",
    )
    action = models.CharField(max_length=255, db_index=True)
    target_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_id = models.CharField(max_length=255, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"{actor_name} performed {self.action} at {self.timestamp}"


class AuditableModel(models.Model):
    """
    Abstract base class/mixin for domain models that should be event-audited on writes.
    """

    class Meta:
        abstract = True


# ============================================================
# Cross-tenant data isolation primitives (issue #1940)
# ============================================================


class TenantQuerySet(models.QuerySet):
    """
    QuerySet that automatically filters by the current tenant.

    The tenant id is read from :mod:`apps.core.tenant` (populated by
    :class:`apps.core.middleware.tenant.TenantContextMiddleware`).

    When no tenant context is active (management commands, background
    jobs, unauthenticated requests), the queryset returns ALL rows —
    this is the "unscoped" mode intended for admin/superuser tooling.
    Production request paths should always have a tenant context.
    """

    def _tenant_id(self):
        # Imported lazily to avoid a circular import at module load.
        from apps.core.tenant import get_current_tenant_id

        return get_current_tenant_id()

    def for_tenant(self, organization_id):
        """Explicitly scope to a specific tenant (useful in scripts/tests)."""
        return self.filter(organization_id=organization_id)

    def unscoped(self):
        """Return the unfiltered queryset (admin/superuser tooling only)."""
        return (
            super().get_queryset()
            if False
            else self.model.objects.using(self._db).all()
        )

    # The core magic: every chained query is auto-scoped.
    def _chain(self, **kwargs):
        qs = super()._chain(**kwargs)
        org_id = qs._tenant_id()
        if org_id is not None:
            return qs.filter(organization_id=org_id)
        return qs


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Manager that returns tenant-scoped querysets by default.

    Use ``TenantModel.objects.unscoped()`` to bypass scoping for
    admin/migration code (rarely needed in request paths).
    """

    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        org_id = None
        try:
            from apps.core.tenant import get_current_tenant_id

            org_id = get_current_tenant_id()
        except Exception:
            org_id = None
        if org_id is not None:
            return qs.filter(organization_id=org_id)
        return qs

    def unscoped(self):
        """Bypass tenant scoping (admin tooling, migrations)."""
        return super().get_queryset()


class TenantAwareModel(models.Model):
    """
    Abstract base class for models that carry per-tenant data.

    Inheriting models get:
        * an ``organization`` FK (the tenant discriminator),
        * a :class:`TenantManager` that auto-filters by the current
          tenant on every request-path query.

    Example::

        class Lesson(TenantAwareModel):
            title = models.CharField(max_length=200)
            # organization FK is added automatically by the base class

        # In a request handler:
        Lesson.objects.all()  # -> only lessons for the current tenant

    For models that cannot be altered (e.g. third-party), use
    :class:`apps.core.mixins.OrganizationScopedQuerySetMixin` on the
    viewset instead — it derives the tenant from ``user__user_profile``
    without requiring an ``organization`` column.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
        db_index=True,
        help_text="The tenant (organization) this record belongs to.",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
