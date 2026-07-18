"""
Models for the OSS Project Health Dashboard.
"""
import uuid

from django.conf import settings
from django.db import models


class RepoHealthScore(models.Model):
    """
    Caches the health analysis of a GitHub repository for fast retrieval.
    Entries are refreshed on request if older than CACHE_TTL_HOURS.
    """

    CACHE_TTL_HOURS = 24

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repo_url = models.URLField(
        unique=True, help_text="The GitHub repository URL (e.g., https://github.com/django/django)."
    )
    repo_owner = models.CharField(max_length=255)
    repo_name = models.CharField(max_length=255)

    # --- Core metrics ---
    open_issues = models.IntegerField(default=0)
    closed_issues = models.IntegerField(default=0)
    open_prs = models.IntegerField(default=0)
    closed_prs = models.IntegerField(default=0)
    avg_pr_close_days = models.FloatField(
        null=True,
        blank=True,
        help_text="Average number of days it takes to merge/close a PR.",
    )
    contributor_count = models.IntegerField(default=0)
    last_commit_days_ago = models.IntegerField(
        null=True, blank=True, help_text="Days since the last commit to the default branch."
    )

    # --- Sentiment ---
    sentiment_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Aggregated TextBlob polarity score of recent PR comments (-1.0 to 1.0).",
    )
    sentiment_label = models.CharField(
        max_length=20,
        blank=True,
        help_text="Human-readable label: 'positive', 'neutral', or 'negative'.",
    )

    # --- Computed score ---
    health_score = models.IntegerField(
        default=0,
        help_text="Overall computed health score out of 100.",
    )
    red_flags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of warning strings for the user (e.g., 'Project appears abandoned').",
    )
    green_flags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of positive strings for the user (e.g., 'Active maintainership').",
    )

    # --- Metadata ---
    analyzed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repo_health_analyses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.repo_owner}/{self.repo_name} (Score: {self.health_score})"
