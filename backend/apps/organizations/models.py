from django.conf import settings
from django.db import models

from apps.core.fields import EncryptedCharField


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


class OrganizationOIDCProvider(models.Model):
    """
    OpenID Connect identity provider that a managed organization signs in with.

    One provider per organization. The client secret is encrypted at rest with
    the field-level key (``FIELD_ENCRYPTION_KEY``), is write-only in the API and
    is never logged. Leave it empty for a public client that relies on PKCE only.
    """

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="oidc_provider"
    )
    # Exact ``issuer`` value of the provider, e.g. https://login.example.com/realm.
    # The discovery document and every ID token must report this same string.
    issuer = models.URLField(max_length=500)
    client_id = models.CharField(max_length=255)
    client_secret = EncryptedCharField(max_length=255, blank=True, default="")
    is_enabled = models.BooleanField(
        default=False  # pyright: ignore[reportArgumentType]
    )
    # Create an account (and org membership) the first time a new person signs in
    # with a verified email on one of the organization's domains.
    auto_provision = models.BooleanField(
        default=True  # pyright: ignore[reportArgumentType]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OIDC provider for {self.organization} ({self.issuer})"


class OrganizationSSODomain(models.Model):
    """
    Email domain routed to an organization's OIDC provider. A domain can belong
    to one organization only, so routing is never ambiguous.
    """

    provider = models.ForeignKey(
        OrganizationOIDCProvider, on_delete=models.CASCADE, related_name="domains"
    )
    domain = models.CharField(max_length=253, unique=True)

    class Meta:
        ordering = ["domain"]

    def __str__(self):
        return str(self.domain)


class OrganizationSSOIdentity(models.Model):
    """
    Link between a local user and a subject at an organization's identity
    provider. This is the only thing a returning SSO login is matched on: never
    the email address, which a provider can change or reassign.
    """

    provider = models.ForeignKey(
        OrganizationOIDCProvider, on_delete=models.CASCADE, related_name="identities"
    )
    # Issuer the subject was issued by, so pointing the provider at a different
    # issuer later cannot reuse an old link.
    # Linking again at the new issuer replaces the old row (see link_existing_user).
    issuer = models.URLField(max_length=500)
    subject = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oidc_identities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "issuer", "subject"],
                name="uniq_sso_identity_subject",
            ),
            models.UniqueConstraint(
                fields=["provider", "user"], name="uniq_sso_identity_user"
            ),
        ]

    def __str__(self):
        return f"{self.user} -> {self.subject}@{self.issuer}"
