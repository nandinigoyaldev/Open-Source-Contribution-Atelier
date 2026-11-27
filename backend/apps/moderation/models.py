from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.audit.chain import MODERATION_CHAIN, ChainedModel

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


class SentimentSnapshot(models.Model):
    """Daily sentiment snapshot."""

    date = models.DateField(auto_now_add=True)
    positive_count = models.IntegerField(default=0)
    negative_count = models.IntegerField(default=0)
    neutral_count = models.IntegerField(default=0)
    avg_toxicity = models.FloatField(default=0)
    total_comments = models.IntegerField(default=0)


class ModerationAuditEvent(ChainedModel):
    """Append only, and hash chained like ``apps.audit.models.AuditEvent``."""

    chain = MODERATION_CHAIN

    # Example values: REPORT_APPROVED, REPORT_DISMISSED
    event_type = models.CharField(max_length=50)

    # SET_NULL, not CASCADE: reports go away with their reporter's account, and
    # the record of what moderators did has to stay.
    content_report = models.ForeignKey(
        ContentReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_audit_events",
    )

    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_moderation_audit_events",
    )

    status_before = models.CharField(max_length=20, null=True, blank=True)
    status_after = models.CharField(max_length=20)

    action_taken = models.CharField(max_length=20, null=True, blank=True)
    reason = models.TextField(blank=True)

    # Not auto_now_add: that would replace the value after it has been hashed.
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    # Ids copied when the row is written. They are hashed, and they stay when the
    # row they point at is deleted.
    content_report_ref = models.BigIntegerField(null=True, editable=False)
    moderator_ref = models.BigIntegerField(null=True, editable=False)
    target_user_ref = models.BigIntegerField(null=True, editable=False)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="idx_created_at"),
            models.Index(fields=["status_after"], name="idx_status_after"),
        ]
