from django.conf import settings

from django.db import models


class OSSIssue(models.Model):
    repo_name = models.CharField(max_length=255)
    issue_number = models.IntegerField()
    title = models.CharField(max_length=512)
    url = models.URLField(max_length=1024)
    labels = models.JSONField(default=list)
    difficulty = models.CharField(max_length=50, blank=True, null=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("repo_name", "issue_number")

    def __str__(self):
        return f"{self.repo_name} #{self.issue_number}: {self.title}"


class Recommendation(models.Model):
    objects = models.Manager()

    class ContentType(models.TextChoices):
        LESSON = "lesson", "Lesson"
        CHALLENGE = "challenge", "Challenge"
        QUIZ = "quiz", "Quiz"
        OSS_ISSUE = "oss_issue", "OSS Issue"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    content_id = models.CharField(max_length=255)  # Assuming slug or id
    title = models.CharField(max_length=255, default="")
    reason = models.TextField()
    priority_score = models.IntegerField(default=0)
    is_dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    github_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    gitlab_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    labels = models.JSONField(default=list)
    language = models.CharField(max_length=50, blank=True)
    difficulty = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-priority_score", "-created_at"]
        unique_together = ("user", "content_type", "content_id")

    def __str__(self):
        return f"{self.user.username} - {self.content_type} {self.title} ({self.priority_score})"
