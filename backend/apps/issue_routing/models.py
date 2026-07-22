"""
Models for smart issue routing and assignment.
"""

from django.db import models
from django.conf import settings

from django.utils import timezone
import uuid


class ExpertiseDomain(models.Model):
    """
    Expertise domains for routing.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    keywords = models.JSONField(default=list)  # Keywords for this domain
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MaintainerExpertise(models.Model):
    """
    Maintainer expertise profile.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expertise"
    )

    # Domains
    primary_domains = models.ManyToManyField(
        ExpertiseDomain, related_name="primary_experts"
    )
    secondary_domains = models.ManyToManyField(
        ExpertiseDomain, related_name="secondary_experts", blank=True
    )

    # Skills
    skills = models.JSONField(default=list)  # List of skill strings

    # Experience
    years_experience = models.FloatField(default=0.0)
    contributions_count = models.IntegerField(default=0)

    # Availability
    is_active = models.BooleanField(default=True)
    max_workload = models.IntegerField(default=5)
    current_workload = models.IntegerField(default=0)

    # Performance
    routing_accuracy = models.FloatField(default=0.0)
    avg_resolution_time = models.FloatField(default=0.0)
    satisfaction_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-routing_accuracy"]

    def __str__(self):
        return f"Expertise: {self.user.username}"

    def can_take_issue(self) -> bool:
        """Check if maintainer can take more issues."""
        return self.is_active and self.current_workload < self.max_workload


class IssueRouting(models.Model):
    """
    Routing record for issues.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("routed", "Routed"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Issue reference
    issue_id = models.CharField(max_length=100, db_index=True)
    issue_number = models.IntegerField()
    issue_title = models.TextField()
    issue_body = models.TextField(blank=True)

    # Routing results
    suggested_maintainers = models.JSONField(
        default=list
    )  # List of user IDs with scores
    primary_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_routed",
    )
    secondary_assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="secondary_routed", blank=True
    )

    # Domain detection
    detected_domains = models.JSONField(default=list)  # List of domain IDs with scores

    # Routing metadata
    routing_score = models.FloatField(default=0.0)
    confidence = models.FloatField(default=0.0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Tracking
    routed_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Feedback
    feedback_score = models.FloatField(null=True, blank=True)
    feedback_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-routed_at"]
        indexes = [
            models.Index(fields=["issue_id", "status"]),
            models.Index(fields=["routing_score"]),
        ]

    def __str__(self):
        return f"Routing: Issue #{self.issue_number} - {self.status}"


class RoutingMetric(models.Model):
    """
    Aggregated routing metrics.
    """

    date = models.DateField(unique=True, db_index=True)

    # Overall metrics
    total_routed = models.IntegerField(default=0)
    successful_routes = models.IntegerField(default=0)
    failed_routes = models.IntegerField(default=0)

    # Resolution metrics
    avg_resolution_time = models.FloatField(default=0.0)
    avg_acceptance_time = models.FloatField(default=0.0)

    # Accuracy metrics
    routing_accuracy = models.FloatField(default=0.0)
    maintainer_satisfaction = models.FloatField(default=0.0)

    # Domain distribution
    domain_distribution = models.JSONField(default=dict)

    # Maintainer workload
    avg_workload = models.FloatField(default=0.0)
    max_workload = models.IntegerField(default=0)
    min_workload = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Routing Metrics: {self.date}"
