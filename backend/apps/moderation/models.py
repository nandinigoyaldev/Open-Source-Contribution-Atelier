from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

User = get_user_model()


class ContentReport(models.Model):
    class Category(models.TextChoices):
        SPAM = "SPAM", "Spam"
        ABUSIVE = "ABUSIVE", "Abusive Language"
        HARASSMENT = "HARASSMENT", "Harassment"
        MISINFORMATION = "MISINFORMATION", "Misinformation"
        PLAGIARISM = "PLAGIARISM", "Plagiarism"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DISMISSED = "DISMISSED", "Dismissed"

    class ActionTaken(models.TextChoices):
        NONE = "NONE", "None"
        HIDDEN = "HIDDEN", "Hidden"
        REMOVED = "REMOVED", "Removed"

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
    )

    # Generic relation to the reported object (e.g., PeerReview, Comment)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    category = models.CharField(max_length=50, choices=Category.choices)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    action_taken = models.CharField(
        max_length=20, choices=ActionTaken.choices, default=ActionTaken.NONE
    )

    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handled_reports",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "content_type", "object_id"],
                name="unique_user_content_report",
            )
        ]

    def __str__(self):
        return f"Report {self.id} - {self.category} on {self.content_type} {self.object_id}"


class ModerationAuditEvent(models.Model):
    # Example values: REPORT_APPROVED, REPORT_DISMISSED
    event_type = models.CharField(max_length=50)

    content_report = models.ForeignKey(
        ContentReport,
        on_delete=models.CASCADE,
        related_name="audit_events",
    )

    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_audit_events",
    )

    status_before = models.CharField(max_length=20, null=True, blank=True)
    status_after = models.CharField(max_length=20)

    action_taken = models.CharField(max_length=20, null=True, blank=True)
    reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["status_after"]),
        ]


