from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class IssueReport(models.Model):
    class IssueType(models.TextChoices):
        BUG = "Bug", "Bug"
        CONTENT = "Content", "Incorrect Content/Typo"
        UI = "UI", "UI/UX Issue"
        SANDBOX = "Sandbox", "Coding Sandbox Issue"
        OTHER = "Other", "Other"

    class Status(models.TextChoices):
        OPEN = "Open", "Open"
        IN_PROGRESS = "In Progress", "In Progress"
        RESOLVED = "Resolved", "Resolved"
        CLOSED = "Closed", "Closed"

    title = models.CharField(max_length=255)
    description = models.TextField()
    issue_type = models.CharField(
        max_length=50, choices=IssueType.choices, default=IssueType.OTHER
    )
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.OPEN
    )
    url_path = models.CharField(
        max_length=1024, blank=True, help_text="URL where the issue occurred"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue_reports",
    )
    image = models.ImageField(upload_to="issue_reports/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.issue_type} - {self.title}"


class Bounty(models.Model):
    class Status(models.TextChoices):
        OPEN = "Open", "Open"
        CLAIMED = "Claimed", "Claimed"
        COMPLETED = "Completed", "Completed"

    title = models.CharField(max_length=255)
    description = models.TextField()
    xp_reward = models.PositiveIntegerField(default=100)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.OPEN
    )
    claimed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claimed_bounties",
    )
    badge = models.ForeignKey(
        "progress.Badge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bounties",
        help_text="Optional badge awarded upon completion of this bounty.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class BountySubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PASSED = "Passed", "Passed"
        FAILED = "Failed", "Failed"

    bounty = models.ForeignKey(
        Bounty, on_delete=models.CASCADE, related_name="submissions"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bounty_submissions"
    )
    code_patch = models.TextField()
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.bounty.title} ({self.status})"
