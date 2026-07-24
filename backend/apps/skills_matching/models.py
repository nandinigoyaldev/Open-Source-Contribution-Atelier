"""
Models for AI-powered contributor skill matching.
"""

from django.db import models
from django.conf import settings

from django.utils import timezone
import uuid


class ContributorProfile(models.Model):
    """
    Contributor profile with GitHub analysis.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_profile"
    )

    # GitHub data
    github_username = models.CharField(max_length=255)
    github_data = models.JSONField(default=dict)

    # Skills
    primary_languages = models.JSONField(default=list)
    all_languages = models.JSONField(default=list)
    frameworks = models.JSONField(default=list)
    skill_levels = models.JSONField(
        default=dict
    )  # {language: 'beginner'|'intermediate'|'advanced'|'expert'}

    # Experience
    total_commits = models.IntegerField(default=0)
    total_repos = models.IntegerField(default=0)
    contributions_count = models.IntegerField(default=0)
    years_experience = models.FloatField(default=0.0)

    # Interests
    interests = models.JSONField(default=list)
    preferred_areas = models.JSONField(default=list)

    # Matching history
    total_recommendations = models.IntegerField(default=0)
    accepted_recommendations = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)

    # Timestamps
    last_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-success_rate"]

    def __str__(self):
        return f"Profile: {self.github_username}"

    def calculate_success_rate(self):
        """Calculate success rate from recommendations."""
        if self.total_recommendations > 0:
            self.success_rate = (
                self.accepted_recommendations / self.total_recommendations
            ) * 100
            self.save(update_fields=["success_rate"])
        return self.success_rate


class SkillTag(models.Model):
    """
    Skill tags for issues.
    """

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50)  # language, framework, tool, domain
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class IssueSkillTag(models.Model):
    """
    Tag issues with required skills.
    """

    issue = models.ForeignKey(
        "ml_triage.Issue", on_delete=models.CASCADE, related_name="skill_tags"
    )
    skill = models.ForeignKey(SkillTag, on_delete=models.CASCADE)
    confidence = models.FloatField(default=0.0)
    auto_tagged = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["issue", "skill"]

    def __str__(self):
        return f"{self.issue} - {self.skill}"


class NewcomerFriendlinessScore(models.Model):
    """
    Score for issue newcomer friendliness.
    """

    issue = models.OneToOneField(
        "ml_triage.Issue", on_delete=models.CASCADE, related_name="friendliness_score"
    )

    # Scores (0-100)
    description_quality = models.FloatField(default=0.0)
    scope_clarity = models.FloatField(default=0.0)
    support_availability = models.FloatField(default=0.0)
    skill_match = models.FloatField(default=0.0)
    overall_score = models.FloatField(default=0.0)

    # Factors
    has_good_first_issue_label = models.BooleanField(default=False)
    has_mentor = models.BooleanField(default=False)
    has_documentation = models.BooleanField(default=False)
    estimated_time_hours = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-overall_score"]

    def __str__(self):
        return f"Friendliness: {self.issue.number} - {self.overall_score:.1f}"

    def calculate_overall(self):
        """Calculate overall friendliness score."""
        self.overall_score = (
            self.description_quality * 0.3
            + self.scope_clarity * 0.25
            + self.support_availability * 0.25
            + self.skill_match * 0.2
        )
        self.save(update_fields=["overall_score"])
        return self.overall_score


class Recommendation(models.Model):
    """
    Skill-based recommendations for contributors.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contributor = models.ForeignKey(
        ContributorProfile, on_delete=models.CASCADE, related_name="recommendations"
    )
    issue = models.ForeignKey("ml_triage.Issue", on_delete=models.CASCADE)

    # Scores
    match_score = models.FloatField(default=0.0)
    friendliness_score = models.FloatField(default=0.0)
    combined_score = models.FloatField(default=0.0)

    # Reasoning
    matched_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    reasoning = models.TextField(blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-combined_score"]

    def __str__(self):
        return f"Recommendation for {self.contributor.github_username}: Issue #{self.issue.number}"

    def accept(self):
        """Accept recommendation."""
        self.status = "accepted"
        self.accepted_at = timezone.now()
        self.save()
        self.contributor.accepted_recommendations += 1
        self.contributor.save()

    def complete(self):
        """Mark recommendation as completed."""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()


class SkillGapAnalysis(models.Model):
    """
    Analysis of skill gaps in the community.
    """

    skill = models.ForeignKey(SkillTag, on_delete=models.CASCADE)
    demand_count = models.IntegerField(default=0)  # Issues needing this skill
    supply_count = models.IntegerField(default=0)  # Contributors with this skill
    gap_score = models.FloatField(default=0.0)  # Demand / Supply ratio
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-gap_score"]

    def __str__(self):
        return f"{self.skill}: {self.gap_score:.2f}"
