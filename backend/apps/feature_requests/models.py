"""
Models for community-driven feature request system with weighted voting.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid
import json


class FeatureRequest(models.Model):
    """
    Feature request with status tracking and voting.
    """

    # Status choices
    STATUS_IDEA = "idea"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_PLANNED = "planned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_IDEA, "Idea"),
        (STATUS_UNDER_REVIEW, "Under Review"),
        (STATUS_PLANNED, "Planned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    # Priority choices
    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_CRITICAL = "critical"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_CRITICAL, "Critical"),
    ]

    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()

    # Author
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feature_requests"
    )

    # Status and priority
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_IDEA, db_index=True
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM
    )

    # Impact vs Effort scoring (1-10)
    impact_score = models.IntegerField(
        default=5, help_text="Impact score (1-10): How impactful is this feature?"
    )
    effort_score = models.IntegerField(
        default=5, help_text="Effort score (1-10): How much effort is required?"
    )

    # Calculated priority score
    priority_score = models.FloatField(
        default=0.0, help_text="Calculated priority score = (impact * weight) / effort"
    )

    # Voting
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    total_votes = models.IntegerField(default=0)
    weighted_votes = models.FloatField(default=0.0)

    # Categories
    category = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Roadmap
    roadmap_quarter = models.CharField(max_length=20, blank=True)
    roadmap_year = models.IntegerField(null=True, blank=True)
    target_release = models.CharField(max_length=50, blank=True)

    # Metadata
    views = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    planned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-priority_score", "-upvotes"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["priority_score"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

    def calculate_priority_score(self):
        """
        Calculate priority score using Impact vs Effort.
        Score = (impact * weight) / effort where weight is based on votes
        """
        # Base weight from votes
        vote_weight = min(self.total_votes / 10, 5) + 1  # 1-6 range

        # Calculate score
        if self.effort_score > 0:
            self.priority_score = (self.impact_score * vote_weight) / self.effort_score
        else:
            self.priority_score = self.impact_score * vote_weight

        self.save(update_fields=["priority_score"])
        return self.priority_score

    def add_vote(self, user, vote_type="upvote"):
        """
        Add a vote to the feature request.

        Args:
            user: User voting
            vote_type: 'upvote' or 'downvote'
        """
        # Check if user already voted
        existing_vote = Vote.objects.filter(feature_request=self, user=user).first()

        if existing_vote:
            # Remove existing vote
            if existing_vote.vote_type == "upvote":
                self.upvotes -= 1
            else:
                self.downvotes -= 1
            self.total_votes -= 1

            # If same type, delete vote (toggle off)
            if existing_vote.vote_type == vote_type:
                existing_vote.delete()
                self.save()
                self.calculate_priority_score()
                return

            # Otherwise, update vote
            existing_vote.delete()

        # Create new vote
        Vote.objects.create(feature_request=self, user=user, vote_type=vote_type)

        if vote_type == "upvote":
            self.upvotes += 1
        else:
            self.downvotes += 1
        self.total_votes += 1

        self.save()
        self.calculate_priority_score()

    def update_status(self, new_status, user=None):
        """
        Update feature request status with timestamp.
        """
        self.status = new_status

        if new_status == self.STATUS_UNDER_REVIEW:
            self.reviewed_at = timezone.now()
        elif new_status == self.STATUS_PLANNED:
            self.planned_at = timezone.now()
        elif new_status == self.STATUS_IN_PROGRESS:
            self.started_at = timezone.now()
        elif new_status == self.STATUS_COMPLETED:
            self.completed_at = timezone.now()

        self.save()

        # Create status history
        StatusHistory.objects.create(
            feature_request=self,
            user=user,
            from_status=self.status,
            to_status=new_status,
        )


class Vote(models.Model):
    """
    User votes on feature requests with weight.
    """

    VOTE_TYPES = [
        ("upvote", "Upvote"),
        ("downvote", "Downvote"),
    ]

    feature_request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE, related_name="votes"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feature_votes"
    )
    vote_type = models.CharField(max_length=10, choices=VOTE_TYPES)

    # Weight based on user role
    weight = models.FloatField(default=1.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["feature_request", "user"]]

    def __str__(self):
        return f"{self.user.username} - {self.vote_type} - {self.feature_request.title}"

    def save(self, *args, **kwargs):
        """Calculate weight based on user role."""
        # Default weight
        self.weight = 1.0

        # Check if user is admin
        if self.user.is_superuser:
            self.weight = 3.0
        elif self.user.groups.filter(name="Moderator").exists():
            self.weight = 2.0
        elif self.user.groups.filter(name="Mentor").exists():
            self.weight = 1.5

        super().save(*args, **kwargs)


class Comment(models.Model):
    """
    Comments on feature requests.
    """

    feature_request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feature_comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content = models.TextField()

    # Upvotes on comments
    upvotes = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.feature_request.title}"


class StatusHistory(models.Model):
    """
    History of status changes for feature requests.
    """

    feature_request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE, related_name="status_history"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="feature_status_changes",
    )
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.feature_request.title}: {self.from_status} → {self.to_status}"


class RoadmapMilestone(models.Model):
    """
    Roadmap milestones for feature planning.
    """

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Date range
    start_date = models.DateField()
    end_date = models.DateField()

    # Quarter and year
    quarter = models.IntegerField(choices=[(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")])
    year = models.IntegerField()

    # Features in this milestone
    features = models.ManyToManyField(
        FeatureRequest, related_name="milestones", blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year", "quarter"]

    def __str__(self):
        return f"Q{self.quarter} {self.year}: {self.name}"

    def get_feature_count(self):
        """Get count of features in this milestone."""
        return self.features.count()

    def get_completion_percentage(self):
        """Get percentage of completed features."""
        total = self.features.count()
        if total == 0:
            return 0
        completed = self.features.filter(status=FeatureRequest.STATUS_COMPLETED).count()
        return (completed / total) * 100
