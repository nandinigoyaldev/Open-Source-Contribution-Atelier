from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from apps.core.models import AdminAuditLog
from apps.core.middleware import get_current_audit_info
from django.contrib import admin


def _is_registered_in_admin(model):
    """Check if a model is registered in the Django admin site."""
    return model in admin.site._registry


@receiver(post_save)
def log_admin_post_save(sender, instance, created, **kwargs):
    if not _is_registered_in_admin(sender):
        return

    audit_info = get_current_audit_info()
    actor = audit_info.get("actor")

    # We only log if there is an active admin user session
    if not actor or not actor.is_authenticated:
        return

    action = "created" if created else "updated"

    AdminAuditLog.objects.create(
        actor=actor,
        action=f"{sender._meta.model_name}_{action}",
        target_type=ContentType.objects.get_for_model(sender),
        target_id=str(instance.pk),
        details={"str": str(instance)},
        ip_address=audit_info.get("ip_address"),
    )


@receiver(post_delete)
def log_admin_post_delete(sender, instance, **kwargs):
    if not _is_registered_in_admin(sender):
        return

    audit_info = get_current_audit_info()
    actor = audit_info.get("actor")

    # We only log if there is an active admin user session
    if not actor or not actor.is_authenticated:
        return

    AdminAuditLog.objects.create(
        actor=actor,
        action=f"{sender._meta.model_name}_deleted",
        target_type=ContentType.objects.get_for_model(sender),
        target_id=str(instance.pk),
        details={"str": str(instance)},
        ip_address=audit_info.get("ip_address"),
    )
