"""
Models for issue quality analysis.
"""

from django.db import models
from django.conf import settings

from django.utils import timezone
import uuid


class IssueQualityCheck(models.Model):
    """
    Quality check results for an issue.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue_title = models.TextField()
    issue_body = models.TextField()
    author = models.CharField(max_length=255)

    # Quality scores
    quality_score = models.FloatField(default=0.0)  # 0-100
    clarity_score = models.FloatField(default=0.0)
    completeness_score = models.FloatField(default=0.0)
    reproducibility_score = models.FloatField(default=0.0)

    # Detection flags
    is_duplicate = models.BooleanField(default=False)
    duplicate_confidence = models.FloatField(default=0.0)
    duplicate_of = models.CharField(max_length=255, blank=True)

    # Language detection
    language = models.CharField(max_length=50, default="en")
    is_english = models.BooleanField(default=True)
    translation_suggestion = models.TextField(blank=True)

    # Environment warnings
    is_user_specific = models.BooleanField(default=False)
    environment_warning = models.TextField(blank=True)

    # Engagement prediction
    predicted_comments = models.IntegerField(default=0)
    predicted_engagement_score = models.FloatField(default=0.0)  # 0-100

    # WONTFIX risk
    wontfix_risk_score = models.FloatField(default=0.0)  # 0-100
    wontfix_reasons = models.JSONField(default=list)

    # Recommendations
    recommendations = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quality Check: {self.issue_title[:50]}"


class DuplicateIssue(models.Model):
    """
    Stored duplicate issues for NLP training.
    """

    issue_id = models.CharField(max_length=100, unique=True)
    title = models.TextField()
    body = models.TextField()
    embedding = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Duplicate: {self.title[:50]}"


class WontfixPattern(models.Model):
    """
    Patterns that lead to WONTFIX labels.
    """

    pattern = models.CharField(max_length=500)
    category = models.CharField(max_length=50)
    frequency = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-frequency"]

    def __str__(self):
        return f"{self.category}: {self.pattern[:50]}"
