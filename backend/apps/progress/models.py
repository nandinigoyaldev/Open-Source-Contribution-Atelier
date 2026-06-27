from apps.content.models import Exercise, Lesson
from apps.organizations.models import Organization
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone


class UserStreak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="streak")
    current_streak = models.PositiveIntegerField(default=0)
    highest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    multiplier = models.FloatField(default=1.0)

    def update_streak(self, activity_date=None):
        if activity_date is None:
            activity_date = timezone.localdate()

        if self.last_activity_date == activity_date:
            return

        if self.last_activity_date:
            delta_days = (activity_date - self.last_activity_date).days
            if delta_days == 1:
                self.current_streak += 1
            elif delta_days > 1:
                self.current_streak = 1
        else:
            self.current_streak = 1

        self.last_activity_date = activity_date

        if self.current_streak > self.highest_streak:
            self.highest_streak = self.current_streak

        if self.current_streak >= 14:
            self.multiplier = 2.0
        elif self.current_streak >= 7:
            self.multiplier = 1.5
        elif self.current_streak >= 3:
            self.multiplier = 1.2
        else:
            self.multiplier = 1.0

        self.save()

    @classmethod
    def get_or_create_for_user(cls, user):
        streak, _ = cls.objects.get_or_create(user=user)
        return streak


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



# ---------------------------------------------------------------------------
# Streak milestone configuration – single source of truth for both the
# StreakEngine and BadgeEvaluator.
# ---------------------------------------------------------------------------
STREAK_MILESTONES = [
    {"days": 3,  "multiplier": 1.2, "label": "3-Day Streak 🔥",  "badge_slug": "streak-3"},
    {"days": 7,  "multiplier": 1.5, "label": "7-Day Streak ⚡",  "badge_slug": "streak-7"},
    {"days": 14, "multiplier": 2.0, "label": "14-Day Streak 💎", "badge_slug": "streak-14"},
    {"days": 30, "multiplier": 2.5, "label": "30-Day Streak 👑", "badge_slug": "streak-30"},
]


class StreakProfile(models.Model):
    """Persisted per-user streak state, updated on each learning activity."""

    objects = models.Manager()

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="streak_profile",
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    current_multiplier = models.FloatField(default=1.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"], name="idx_streak_profile_user"),
        ]

    def __str__(self) -> str:
        return (
            f"StreakProfile({self.user.username}, "
            f"streak={self.current_streak}, "
            f"multiplier={self.current_multiplier}x)"
        )


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


class PlagiarismReport(models.Model):
    objects = models.Manager()
    submission = models.ForeignKey(CodeSubmission, on_delete=models.CASCADE, related_name="plagiarism_reports")
    matched_submission = models.ForeignKey(CodeSubmission, on_delete=models.CASCADE, related_name="matched_in_reports")
    similarity_score = models.FloatField()
    is_flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-similarity_score"]
        unique_together = ("submission", "matched_submission")

    def __str__(self):
        return f"PlagiarismReport: {self.submission.id} vs {self.matched_submission.id} ({self.similarity_score:.2f})"

