from django.contrib.auth.models import User
from django.db import models

from apps.organizations.models import Organization


class Permission(models.Model):
    objects = models.Manager()
    slug = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug


class Role(models.Model):
    objects = models.Manager()
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    is_system_role = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    objects = models.Manager()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_roles",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role", "organization")

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class AuditLog(models.Model):
    objects = models.Manager()
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rbac_actions_performed",
    )
    target_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="rbac_actions_received"
    )
    action = models.CharField(max_length=50)  # 'assign' or 'revoke'
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.actor} {self.action} {self.role} to {self.target_user}"
