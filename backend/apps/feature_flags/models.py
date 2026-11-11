from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class FeatureFlag(models.Model):
    FLAG_TYPE_CHOICES = [
        ("boolean", "Boolean"),
        ("percentage", "Percentage Rollout"),
        ("organization", "Organization Targeting"),
        ("user", "User Targeting"),
    ]

    name = models.CharField(max_length=128, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")
    flag_type = models.CharField(
        max_length=32, choices=FLAG_TYPE_CHOICES, default="boolean"
    )
    is_active = models.BooleanField(default=False)
    default_value = models.BooleanField(default=False)
    rollout_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of users or entities targeted (0 to 100).",
    )
    target_organizations = models.JSONField(
        default=list,
        blank=True,
        help_text="List of organization slugs or IDs allowed for this flag.",
    )
    target_users = models.JSONField(
        default=list,
        blank=True,
        help_text="List of user IDs or usernames allowed for this flag.",
    )
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_flags",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"

    def __str__(self):
        return f"{self.name} ({'ACTIVE' if self.is_active else 'INACTIVE'})"


class FeatureFlagAuditLog(models.Model):
    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("rolled_back", "Rolled Back"),
        ("approved", "Approved"),
    ]

    flag = models.ForeignKey(
        FeatureFlag, on_delete=models.CASCADE, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="feature_flag_audit_logs",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    scope = models.CharField(
        max_length=64,
        default="global",
        help_text="Scope of the change e.g. 'global', 'organization', 'percentage'.",
    )
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Feature Flag Audit Log"
        verbose_name_plural = "Feature Flag Audit Logs"

    def __str__(self):
        actor_name = self.actor.username if self.actor else "system"
        return f"[{self.timestamp}] {self.flag.name} - {self.action} by {actor_name}"
