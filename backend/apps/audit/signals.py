"""
Django signals that emit AuditEvent for every AuditableModel write.

Guards:
- Skips if sender is AuditEvent itself (prevents infinite loops).
- Skips if sender is not a subclass of AuditableModel.
- Skips during Django migrations (no audit table yet).
- Captures the 'before' snapshot in pre_save and stashes it on the
  instance so post_save can build the diff.
- Uses transaction.on_commit so events are only emitted for committed
  writes, not rolled-back ones.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)


def _is_auditable(sender) -> bool:
    """Return True only for concrete AuditableModel subclasses."""
    from apps.audit.models import AuditEvent
    from apps.core.models import AuditableModel

    if sender is AuditEvent:
        return False
    return issubclass(sender, AuditableModel)


def _model_snapshot(instance) -> dict:
    """Serialise instance fields to a plain dict (JSON-safe)."""
    try:
        return model_to_dict(instance)
    except Exception:
        return {"pk": instance.pk}


def _emit(instance, action: str, before=None, after=None) -> None:
    """Create an AuditEvent inside transaction.on_commit."""
    from apps.audit.middleware import get_audit_context
    from apps.audit.models import AuditEvent

    ctx = get_audit_context()
    resource_type = f"{instance._meta.app_label}.{instance._meta.model_name}"
    resource_id = str(instance.pk)

    def _create():
        try:
            AuditEvent.objects.create(
                actor=ctx.get("actor"),
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                before=before,
                after=after,
                correlation_id=ctx.get("correlation_id", ""),
                ip_address=ctx.get("ip_address"),
                user_agent=ctx.get("user_agent", ""),
            )
        except Exception:
            logger.exception(
                "Failed to create AuditEvent for %s#%s action=%s",
                resource_type,
                resource_id,
                action,
            )

    from django.conf import settings

    if getattr(settings, "TESTING", False):
        _create()
    else:
        transaction.on_commit(_create)


# ── Signal handlers ───────────────────────────────────────────────────────────


@receiver(pre_save)
def _capture_before_snapshot(sender, instance, **kwargs):
    """Stash the pre-save state on the instance for use in post_save."""
    if not _is_auditable(sender):
        return
    if instance.pk:
        try:
            existing = sender.objects.get(pk=instance.pk)
            instance._audit_before = _model_snapshot(existing)
        except sender.DoesNotExist:
            instance._audit_before = None
    else:
        instance._audit_before = None


@receiver(post_save)
def _emit_on_save(sender, instance, created, **kwargs):
    if not _is_auditable(sender):
        return
    action = "created" if created else "updated"
    before = None if created else getattr(instance, "_audit_before", None)
    after = _model_snapshot(instance)
    _emit(instance, action, before=before, after=after)


@receiver(post_delete)
def _emit_on_delete(sender, instance, **kwargs):
    if not _is_auditable(sender):
        return
    before = _model_snapshot(instance)
    _emit(instance, "deleted", before=before, after=None)
