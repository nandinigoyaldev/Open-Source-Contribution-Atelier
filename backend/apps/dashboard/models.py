from django.contrib.auth.models import User
from django.db import models


class Issue(models.Model):
    objects = models.Manager()

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        SOLVED = "solved", "Solved"

    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    points = models.PositiveIntegerField(default=50)
    bonus_points = models.PositiveIntegerField(
        default=0, help_text="Bonus points awarded during a multiplier event."
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_issues",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    class Meta:
        indexes = [
            models.Index(
                fields=["assigned_to", "status"], name="idx_issue_assignee_status"
            ),
            models.Index(
                fields=["status", "-created_at"], name="idx_issue_status_time"
            ),
        ]


class PullRequest(models.Model):
    objects = models.Manager()

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        MERGED = "merged", "Merged"
        CLOSED = "closed", "Closed"

    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    issue = models.ForeignKey(
        Issue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pull_requests",
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pull_requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    merged_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"], name="idx_pr_user_status"),
            models.Index(fields=["issue", "status"], name="idx_pr_issue_status"),
            models.Index(fields=["status", "-created_at"], name="idx_pr_status_time"),
        ]


class StreakFreeze(models.Model):
    objects = models.Manager()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="streak_freezes"
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    used_on_date = models.DateField(null=True, blank=True)
    cost = models.PositiveIntegerField(default=100)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "used_on_date"], name="idx_streak_freeze_user_date"
            ),
        ]

    def __str__(self):
        return f"StreakFreeze({self.user.username}, used={self.used_on_date})"
