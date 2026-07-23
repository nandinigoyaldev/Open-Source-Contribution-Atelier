"""
Models for developer onboarding journey tracking.
"""

from django.db import models
from django.conf import settings

from django.utils import timezone
import uuid


class OnboardingJourney(models.Model):
    """
    Track developer onboarding journey.
    """

    STAGES = [
        ("discovery", "Discovery"),
        ("setup", "Setup"),
        ("first_issue", "First Issue"),
        ("pr_submitted", "PR Submitted"),
        ("merged", "Merged"),
        ("completed", "Completed"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("stuck", "Stuck"),
        ("abandoned", "Abandoned"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="onboarding"
    )

    # Current stage
    current_stage = models.CharField(max_length=20, choices=STAGES, default="discovery")
    stage_started_at = models.DateTimeField(auto_now_add=True)

    # Stage completion timestamps
    discovery_completed_at = models.DateTimeField(null=True, blank=True)
    setup_completed_at = models.DateTimeField(null=True, blank=True)
    first_issue_completed_at = models.DateTimeField(null=True, blank=True)
    pr_submitted_at = models.DateTimeField(null=True, blank=True)
    merged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Time spent in each stage (minutes)
    discovery_duration = models.IntegerField(default=0)
    setup_duration = models.IntegerField(default=0)
    first_issue_duration = models.IntegerField(default=0)
    pr_duration = models.IntegerField(default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Completion prediction
    completion_score = models.FloatField(default=0.0)
    predicted_completion_date = models.DateTimeField(null=True, blank=True)

    # Drop-off detection
    is_dropped_off = models.BooleanField(default=False)
    dropped_off_at = models.DateTimeField(null=True, blank=True)
    dropoff_reason = models.TextField(blank=True)

    # Health score (0-100)
    health_score = models.FloatField(default=0.0)

    # Nudges
    nudges_sent = models.JSONField(default=list)
    last_nudge_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["current_stage", "status"]),
            models.Index(fields=["completion_score"]),
            models.Index(fields=["health_score"]),
        ]

    def __str__(self):
        return f"Onboarding: {self.user.username} - {self.current_stage}"

    def advance_stage(self, new_stage: str):
        """Advance to next stage."""
        # Calculate duration
        if self.stage_started_at:
            duration = (timezone.now() - self.stage_started_at).total_seconds() / 60
            stage_field = f"{self.current_stage}_duration"
            if hasattr(self, stage_field):
                setattr(self, stage_field, duration)

        # Update timestamps
        if new_stage == "setup":
            self.discovery_completed_at = timezone.now()
        elif new_stage == "first_issue":
            self.setup_completed_at = timezone.now()
        elif new_stage == "pr_submitted":
            self.first_issue_completed_at = timezone.now()
        elif new_stage == "merged":
            self.pr_submitted_at = timezone.now()
        elif new_stage == "completed":
            self.merged_at = timezone.now()
            self.completed_at = timezone.now()
            self.status = "completed"

        self.current_stage = new_stage
        self.stage_started_at = timezone.now()
        self.save()

    def calculate_health_score(self) -> float:
        """Calculate onboarding health score."""
        score = 0.0

        # Stage completion (max 40 points)
        stage_weights = {
            "discovery": 10,
            "setup": 20,
            "first_issue": 30,
            "pr_submitted": 40,
            "merged": 50,
            "completed": 60,
        }
        score += stage_weights.get(self.current_stage, 0) / 60 * 40

        # Time efficiency (max 30 points)
        if self.created_at:
            days = (timezone.now() - self.created_at).days
            if days <= 1:
                score += 30
            elif days <= 3:
                score += 20
            elif days <= 7:
                score += 10

        # Engagement (max 30 points)
        if self.nudges_sent:
            engagement = len([n for n in self.nudges_sent if n.get("responded", False)])
            score += min(engagement * 10, 30)

        self.health_score = min(100, score)
        self.save(update_fields=["health_score"])
        return self.health_score


class JourneyEvent(models.Model):
    """
    Individual events in the onboarding journey.
    """

    EVENT_TYPES = [
        ("fork", "Forked Repository"),
        ("clone", "Cloned Repository"),
        ("setup", "Environment Setup"),
        ("issue_view", "Viewed Issue"),
        ("issue_comment", "Commented on Issue"),
        ("pr_open", "Opened PR"),
        ("pr_update", "Updated PR"),
        ("pr_review", "PR Reviewed"),
        ("pr_merge", "PR Merged"),
        ("help_seek", "Sought Help"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(
        OnboardingJourney, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    event_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.event_type} - {self.journey.user.username}"


class OnboardingNudge(models.Model):
    """
    Personalized nudges for contributors.
    """

    TYPE_CHOICES = [
        ("encouragement", "Encouragement"),
        ("reminder", "Reminder"),
        ("suggestion", "Suggestion"),
        ("resource", "Resource"),
        ("checkin", "Check-in"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(
        OnboardingJourney, on_delete=models.CASCADE, related_name="nudges"
    )
    nudge_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    action_url = models.URLField(blank=True)
    is_sent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nudge_type} - {self.journey.user.username}"


class OnboardingMetric(models.Model):
    """
    Aggregated onboarding metrics.
    """

    date = models.DateField(unique=True, db_index=True)

    # Active contributors
    active_contributors = models.IntegerField(default=0)
    new_contributors = models.IntegerField(default=0)

    # Stage distribution
    discovery_count = models.IntegerField(default=0)
    setup_count = models.IntegerField(default=0)
    first_issue_count = models.IntegerField(default=0)
    pr_submitted_count = models.IntegerField(default=0)
    merged_count = models.IntegerField(default=0)

    # Drop-off rates
    discovery_dropoff = models.FloatField(default=0.0)
    setup_dropoff = models.FloatField(default=0.0)
    first_issue_dropoff = models.FloatField(default=0.0)
    pr_dropoff = models.FloatField(default=0.0)

    # Average durations (hours)
    avg_discovery_duration = models.FloatField(default=0.0)
    avg_setup_duration = models.FloatField(default=0.0)
    avg_first_issue_duration = models.FloatField(default=0.0)
    avg_pr_duration = models.FloatField(default=0.0)

    # Success rates
    completion_rate = models.FloatField(default=0.0)
    retention_rate = models.FloatField(default=0.0)

    # Health scores
    average_health_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Metrics: {self.date}"
