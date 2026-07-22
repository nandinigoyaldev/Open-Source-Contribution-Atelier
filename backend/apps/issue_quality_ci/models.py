"""
Models for CI/CD issue quality pipeline.
"""

from django.db import models
from django.utils import timezone
import uuid


class IssueQualityRecord(models.Model):
    """
    Record of issue quality analysis.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Issue metadata
    issue_id = models.CharField(max_length=100, db_index=True)
    repository = models.CharField(max_length=255)
    issue_number = models.IntegerField()
    issue_title = models.TextField()
    issue_body = models.TextField()
    issue_author = models.CharField(max_length=255)

    # Quality scores (0-100)
    clarity_score = models.FloatField(default=0.0)
    scope_score = models.FloatField(default=0.0)
    acceptance_criteria_score = models.FloatField(default=0.0)
    touchpoints_score = models.FloatField(default=0.0)
    overall_quality_score = models.FloatField(default=0.0)

    # Accessibility scores (0-100)
    language_accessibility = models.FloatField(default=0.0)
    inclusivity_score = models.FloatField(default=0.0)

    # Issues detected
    clarity_issues = models.JSONField(default=list)
    scope_issues = models.JSONField(default=list)
    acceptance_issues = models.JSONField(default=list)

    # Recommendations
    suggestions = models.JSONField(default=list)

    # Success metrics
    time_to_close_hours = models.FloatField(null=True, blank=True)
    comments_needed = models.IntegerField(default=0)
    pr_quality_score = models.FloatField(null=True, blank=True)

    # Status
    is_improved = models.BooleanField(default=False)
    quality_improvement = models.FloatField(default=0.0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["issue_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["overall_quality_score"]),
        ]

    def __str__(self):
        return f"Quality: #{self.issue_number} - {self.overall_quality_score:.1f}"


class QualityMetric(models.Model):
    """
    Aggregated quality metrics.
    """

    date = models.DateField(unique=True, db_index=True)

    # Overall metrics
    average_quality_score = models.FloatField(default=0.0)
    total_issues = models.IntegerField(default=0)

    # Distribution
    high_quality_count = models.IntegerField(default=0)  # >70
    medium_quality_count = models.IntegerField(default=0)  # 40-70
    low_quality_count = models.IntegerField(default=0)  # <40

    # Accessibility
    average_accessibility_score = models.FloatField(default=0.0)
    accessibility_issues_count = models.IntegerField(default=0)

    # Success metrics
    average_time_to_close = models.FloatField(default=0.0)
    average_comments_needed = models.FloatField(default=0.0)
    average_pr_quality = models.FloatField(default=0.0)

    # Improvement
    quality_improvement_rate = models.FloatField(default=0.0)
    issues_improved = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Metrics: {self.date} - {self.average_quality_score:.1f}"


class QualityComment(models.Model):
    """
    Comments about issue quality.
    """

    issue = models.ForeignKey(
        IssueQualityRecord, on_delete=models.CASCADE, related_name="quality_comments"
    )
    comment_type = models.CharField(max_length=50)  # suggestion, warning, improvement
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.comment_type}: {self.content[:50]}"


class QualityTrend(models.Model):
    """
    Quality trends over time.
    """

    period = models.CharField(max_length=20)  # weekly, monthly
    start_date = models.DateField()
    end_date = models.DateField()

    # Trend data
    quality_trend = models.JSONField(default=list)  # [{date, score}]
    metric_trend = models.JSONField(default=list)  # [{date, metric}]
    improvement_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trend: {self.period} - {self.start_date} to {self.end_date}"
