import logging
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import OrganizationMembership

logger = logging.getLogger(__name__)


def invalidate_user_organization_rbac_cache(user_id, organization_id=None):
    """
    Invalidates all cached permissions, roles, and memberships for a user
    when their organization membership or role is modified.
    """
    if not user_id:
        return

    cache_keys = [
        f"rbac:user_roles:{user_id}",
        f"rbac:user_perms:{user_id}",
        f"user_permissions:{user_id}",
        f"user_roles:{user_id}",
    ]

    if organization_id:
        cache_keys.extend([
            f"org:membership:{user_id}:{organization_id}",
            f"org:user_role:{user_id}:{organization_id}",
            f"user_org_membership:{user_id}:{organization_id}",
            f"rbac:user_org_role:{user_id}:{organization_id}",
        ])

    cache.delete_many(cache_keys)
    logger.debug(
        f"Invalidated RBAC and organization permission cache for user {user_id} (org {organization_id})"
    )


@receiver(post_save, sender=OrganizationMembership)
def organization_membership_post_save(sender, instance, created, **kwargs):
    invalidate_user_organization_rbac_cache(
        user_id=instance.user_id,
        organization_id=instance.organization_id,
    )


@receiver(post_delete, sender=OrganizationMembership)
def organization_membership_post_delete(sender, instance, **kwargs):
    invalidate_user_organization_rbac_cache(
        user_id=instance.user_id,
        organization_id=instance.organization_id,
    )
