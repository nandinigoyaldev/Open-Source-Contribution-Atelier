from apps.content.models import Exercise, Lesson
from apps.organizations.models import Organization
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone


class XPMultiplierEvent(models.Model):
    name = models.CharField(max_length=255)
    multiplier = models.FloatField(default=1.5)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.name} ({self.multiplier}x)"

    @classmethod
    def get_active_multiplier(cls) -> float:
        now = timezone.now()
        active_event = cls.objects.filter(
            is_active=True, start_time__lte=now, end_time__gte=now
        ).first()
        return active_event.multiplier if active_event else 1.0


class Badge(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = models.Manager()
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.CharField(max_length=100, default="general")
    icon_asset_url = models.URLField(blank=True, default="")


class UserBadge(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = models.Manager()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="earned_badges"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="earned_by")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")


class LessonProgress(models.Model):
    objects = models.Manager()
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    score = models.PositiveIntegerField(default=0)
    base_score = models.PositiveIntegerField(default=0)
    multiplier_applied = models.FloatField(default=1.0)
    attempt_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson"],
                name="unique_user_lesson_progress",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "completed"], name="idx_progress_user_completed"
            ),
            models.Index(fields=["user", "score"], name="idx_progress_user_score"),
            models.Index(
                fields=["user", "-updated_at"], name="idx_progress_user_updated"
            ),
        ]


class ExerciseAttempt(models.Model):
    objects = models.Manager()
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    submitted_command = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "exercise", "is_correct"],
                name="idx_ex_attempt_user_correct",
            ),
            models.Index(
                fields=["user", "-created_at"], name="idx_ex_attempt_user_time"
            ),
        ]


class HelpRequest(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = models.Manager()

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="help_requests"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="help_requests"
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"], name="idx_help_req_user_status"),
            models.Index(
                fields=["status", "-created_at"], name="idx_help_req_status_time"
            ),
        ]


class QuizAttempt(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = models.Manager()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="quiz_attempts"
    )
    question_id = models.CharField(max_length=255)
    question_text = models.TextField()
    selected_answer = models.CharField(max_length=255)
    correct_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_correct"], name="idx_quiz_user_correct"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.question_id} - {'✓' if self.is_correct else '✗'}"


import uuid


class Certificate(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = models.Manager()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="certificates"
    )
    course_name = models.CharField(
        max_length=255, default="Open Source Contribution Course"
    )
    verification_hash = models.CharField(
        max_length=64, unique=True, default=uuid.uuid4, db_index=True
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Certificate for {self.user.username} - {self.verification_hash}"


class CodeSubmission(models.Model):
    objects = models.Manager()

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWED = "reviewed", "Reviewed"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="code_submissions"
    )
    title = models.CharField(max_length=255)
    code_snippet = models.TextField()
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} by {self.user.username}"


class PeerReview(models.Model):
    objects = models.Manager()
    submission = models.ForeignKey(
        CodeSubmission, on_delete=models.CASCADE, related_name="reviews"
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="given_reviews"
    )
    feedback = models.TextField()
    rating = models.PositiveIntegerField(default=5)
    points_earned = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("submission", "reviewer")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.submission.title}"
