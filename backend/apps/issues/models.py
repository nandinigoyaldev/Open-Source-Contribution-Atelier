from django.db import models
from django.contrib.auth import get_user_model

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
