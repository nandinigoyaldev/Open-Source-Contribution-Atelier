"""
Models for contributor burnout detection.
"""

from django.db import models
from django.conf import settings

from django.utils import timezone
import uuid


class ContributorActivity(models.Model):
    """
    Track contributor activity patterns.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_records",
    )

    # Activity metrics
    commits_last_week = models.IntegerField(default=0)
    commits_last_month = models.IntegerField(default=0)
    reviews_last_week = models.IntegerField(default=0)
    reviews_last_month = models.IntegerField(default=0)
    comments_last_week = models.IntegerField(default=0)
    comments_last_month = models.IntegerField(default=0)

    # Response times (hours)
    avg_response_time = models.FloatField(default=0.0)
    avg_review_response_time = models.FloatField(default=0.0)

    # Activity trends
    activity_trend = models.FloatField(
        default=0.0
    )  # Positive = increasing, Negative = decreasing
    review_trend = models.FloatField(default=0.0)
    response_trend = models.FloatField(default=0.0)

    # Sentiment scores (-1 to 1)
    sentiment_score = models.FloatField(default=0.0)
    sentiment_trend = models.FloatField(default=0.0)

    # Burnout indicators
    burnout_score = models.FloatField(default=0.0)  # 0-100
    burnout_risk = models.CharField(
        max_length=20, default="low"
    )  # low, medium, high, critical

    # Detection
    detected_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-burnout_score"]
        indexes = [
            models.Index(fields=["user", "burnout_score"]),
            models.Index(fields=["burnout_risk"]),
        ]

    def __str__(self):
        return f"Activity: {self.user.username} - {self.burnout_risk}"


class BurnoutSignal(models.Model):
    """
    Detected burnout signals.
    """

    SIGNAL_TYPES = [
        ("declining_activity", "Declining Activity"),
        ("negative_sentiment", "Negative Sentiment"),
        ("increased_response_time", "Increased Response Time"),
        ("reduced_reviews", "Reduced Reviews"),
        ("irregular_pattern", "Irregular Pattern"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="burnout_signals",
    )
    signal_type = models.CharField(max_length=30, choices=SIGNAL_TYPES)
    severity = models.CharField(max_length=20)  # mild, moderate, severe
    description = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.signal_type} - {self.user.username}"


class Intervention(models.Model):
    """
    Automated interventions for burnout.
    """

    TYPE_CHOICES = [
        ("encouragement", "Encouragement"),
        ("workload_reduction", "Workload Reduction"),
        ("break_suggestion", "Break Suggestion"),
        ("support_offer", "Support Offer"),
        ("resource_sharing", "Resource Sharing"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("acknowledged", "Acknowledged"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interventions"
    )
    signal = models.ForeignKey(
        BurnoutSignal, on_delete=models.CASCADE, related_name="interventions"
    )
    intervention_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.intervention_type} - {self.user.username}"


class BurnoutMetric(models.Model):
    """
    Aggregated burnout metrics.
    """

    date = models.DateField(unique=True, db_index=True)

    # Overall metrics
    total_contributors = models.IntegerField(default=0)
    at_risk_contributors = models.IntegerField(default=0)
    critical_contributors = models.IntegerField(default=0)

    # Risk distribution
    low_risk_count = models.IntegerField(default=0)
    medium_risk_count = models.IntegerField(default=0)
    high_risk_count = models.IntegerField(default=0)
    critical_risk_count = models.IntegerField(default=0)

    # Average scores
    average_burnout_score = models.FloatField(default=0.0)
    average_sentiment = models.FloatField(default=0.0)

    # Trends
    burnout_trend = models.FloatField(default=0.0)
    sentiment_trend = models.FloatField(default=0.0)

    # Interventions
    total_interventions = models.IntegerField(default=0)
    successful_interventions = models.IntegerField(default=0)
    intervention_success_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Burnout Metrics: {self.date}"
