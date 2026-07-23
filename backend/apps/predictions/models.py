from django.db import models
from django.utils import timezone


class ReviewerAvailability(models.Model):
    reviewer_username = models.CharField(max_length=150, unique=True)
    current_workload = models.IntegerField(default=0, help_text="Number of open PR reviews currently assigned")
    activity_score = models.FloatField(default=1.0, help_text="Activity score (0.0 to 1.0 based on recent activity)")
    avg_response_time_hours = models.FloatField(default=24.0, help_text="Historical average response time in hours")
    last_active_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Reviewer Availabilities"
        ordering = ["-activity_score", "current_workload"]

    def __str__(self):
        return f"{self.reviewer_username} (Workload: {self.current_workload})"

    def recalculate_workload(self):
        self.current_workload = self.assigned_prs.filter(status="OPEN").count()
        self.save(update_fields=["current_workload"])


class PullRequestMetric(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("MERGED", "Merged"),
        ("CLOSED", "Closed"),
    ]

    repo_name = models.CharField(max_length=150, default="default")
    pr_number = models.IntegerField()
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=150)
    assigned_reviewer = models.ForeignKey(
        ReviewerAvailability,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_prs",
    )
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    changed_files = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    actual_review_delay_hours = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-pr_number"]
        unique_together = [("repo_name", "pr_number")]

    def __str__(self):
        return f"{self.repo_name}#PR {self.pr_number}: {self.title}"

    @property
    def total_lines_changed(self):
        return self.additions + self.deletions

    def mark_as_completed(self, status_val="MERGED"):
        now = timezone.now()
        if self.created_at:
            delta_seconds = (now - self.created_at).total_seconds()
            self.actual_review_delay_hours = round(max(0.1, delta_seconds / 3600.0), 1)
        self.status = status_val
        self.save()
        if self.assigned_reviewer:
            self.assigned_reviewer.recalculate_workload()


class ReviewDelayPrediction(models.Model):
    RISK_LEVEL_CHOICES = [
        ("LOW", "Low Risk"),
        ("MEDIUM", "Medium Risk"),
        ("HIGH", "High Risk"),
        ("CRITICAL", "Critical Stagnation Risk"),
    ]

    pr = models.ForeignKey(
        PullRequestMetric,
        on_delete=models.CASCADE,
        related_name="predictions",
    )
    predicted_delay_hours = models.FloatField()
    confidence_interval_hours = models.FloatField(default=12.0)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="LOW")
    features_used = models.JSONField(default=dict)
    predicted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-predicted_at"]

    def __str__(self):
        return f"Prediction for PR #{self.pr.pr_number}: {self.predicted_delay_hours:.1f}h (±{self.confidence_interval_hours:.1f}h)"


class DelayAlert(models.Model):
    prediction = models.ForeignKey(
        ReviewDelayPrediction,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    alert_type = models.CharField(max_length=50, default="HIGH_STAGNATION_RISK")
    message = models.TextField()
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Alert ({self.alert_type}) - PR #{self.prediction.pr.pr_number}"
