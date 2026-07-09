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
