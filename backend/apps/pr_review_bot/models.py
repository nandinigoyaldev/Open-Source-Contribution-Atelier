"""
Models for PR review bot.
"""

from django.db import models
from django.conf import settings

from django.utils import timezone
import uuid


class PRReview(models.Model):
    """
    PR review record.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PR metadata
    pr_number = models.IntegerField()
    repository = models.CharField(max_length=255)
    pr_title = models.TextField()
    pr_description = models.TextField(blank=True)
    pr_author = models.CharField(max_length=255)
    pr_url = models.URLField()

    # Review status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Review results
    quality_score = models.FloatField(default=0.0)
    complexity_score = models.FloatField(default=0.0)
    duplication_score = models.FloatField(default=0.0)
    security_score = models.FloatField(default=0.0)
    test_coverage_score = models.FloatField(default=0.0)

    # Issues found
    style_issues = models.JSONField(default=list)
    complexity_issues = models.JSONField(default=list)
    duplication_issues = models.JSONField(default=list)
    security_issues = models.JSONField(default=list)
    test_issues = models.JSONField(default=list)

    # Recommendations
    recommendations = models.JSONField(default=list)
    summary = models.TextField(blank=True)

    # Comments
    comments_posted = models.JSONField(default=list)
    comment_count = models.IntegerField(default=0)

    # Metadata
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pr_number", "repository"]),
            models.Index(fields=["status"]),
            models.Index(fields=["quality_score"]),
        ]

    def __str__(self):
        return f"PR #{self.pr_number} - {self.quality_score:.1f}%"


class CodeIssue(models.Model):
    """
    Individual code issue found by the bot.
    """

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    ]

    TYPE_CHOICES = [
        ("style", "Style"),
        ("complexity", "Complexity"),
        ("duplication", "Duplication"),
        ("security", "Security"),
        ("test", "Test"),
        ("performance", "Performance"),
        ("maintainability", "Maintainability"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        PRReview, on_delete=models.CASCADE, related_name="issues"
    )

    # Issue details
    issue_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    file_path = models.CharField(max_length=500)
    line_number = models.IntegerField(null=True, blank=True)
    code_snippet = models.TextField(blank=True)

    # Suggestion
    suggestion = models.TextField(blank=True)
    suggested_code = models.TextField(blank=True)

    # Status
    is_fixed = models.BooleanField(default=False)
    fixed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-severity"]
        indexes = [
            models.Index(fields=["review", "issue_type"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self):
        return f"{self.issue_type}: {self.title[:50]}"


class PRReviewComment(models.Model):
    """
    Comments posted by the bot on PR.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        PRReview, on_delete=models.CASCADE, related_name="bot_comments"
    )

    # Comment details
    comment_id = models.CharField(max_length=100, unique=True)
    file_path = models.CharField(max_length=500, blank=True)
    line_number = models.IntegerField(null=True, blank=True)
    body = models.TextField()

    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment {self.comment_id} on PR #{self.review.pr_number}"


class ReviewConfig(models.Model):
    """
    Configuration for PR review bot.
    """

    repository = models.CharField(max_length=255, unique=True)

    # Enabled checks
    check_style = models.BooleanField(default=True)
    check_complexity = models.BooleanField(default=True)
    check_duplication = models.BooleanField(default=True)
    check_security = models.BooleanField(default=True)
    check_tests = models.BooleanField(default=True)

    # Thresholds
    max_complexity = models.IntegerField(default=10)
    max_duplication = models.IntegerField(default=30)
    min_test_coverage = models.IntegerField(default=80)

    # Auto-comment settings
    auto_comment = models.BooleanField(default=True)
    comment_on_issues = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Config for {self.repository}"
