from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """
    Links a user to an organization with a specific role. This is the
    source of truth for organization access control — OrganizationViewSet
    scopes its queryset and permissions off this model rather than off
    Organization directly.
    """

    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_MEMBER, "Member"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "user")
        ordering = ["-role", "joined_at"]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"

    @property
    def is_admin_or_owner(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)


class OrganizationAuditLog(models.Model):
    """
    Append-only audit trail of changes made to an organization
    (creation, updates, membership/role changes, deletion).
    """

    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_DELETED = "deleted"
    ACTION_MEMBER_ADDED = "member_added"
    ACTION_MEMBER_REMOVED = "member_removed"
    ACTION_MEMBER_ROLE_CHANGED = "member_role_changed"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_DELETED, "Deleted"),
        (ACTION_MEMBER_ADDED, "Member added"),
        (ACTION_MEMBER_REMOVED, "Member removed"),
        (ACTION_MEMBER_ROLE_CHANGED, "Member role changed"),
    ]

    # Nullable + no related_name back-reference cleanup needed on delete:
    # we intentionally keep the audit trail even after the org is gone,
    # so we store the org id/name as plain fields rather than a hard FK
    # that would cascade-delete the log along with the organization.
    organization_id = models.IntegerField(db_index=True)
    organization_name = models.CharField(max_length=100)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_audit_actions",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} on {self.organization_name} by {self.actor}"
