from django.contrib.auth.models import User
from django.db import models

from apps.organizations.models import Organization


class Challenge(models.Model):
    objects = models.Manager()
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    difficulty = models.CharField(max_length=32)
    points = models.PositiveIntegerField(default=50)
    is_featured = models.BooleanField(default=False)


class ChallengeOfTheDay(models.Model):
    """One record per calendar date, set by admin."""

    objects = models.Manager()
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    date = models.DateField(unique=True)
    bonus_points = models.PositiveIntegerField(
        default=50, help_text="Extra XP awarded for completing today's challenge."
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.date} → {self.challenge.title}"


class ChallengeCompletion(models.Model):
    """Tracks whether a user completed a specific challenge and earned bonus XP."""

    objects = models.Manager()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="challenge_completions"
    )
    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="completions"
    )
    bonus_earned = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "challenge")
        ordering = ["-completed_at"]

    def __str__(self) -> str:
        return f"{self.user.username} completed {self.challenge.title} (+{self.bonus_earned} bonus)"
