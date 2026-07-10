from __future__ import annotations
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


from apps.content.models import Exercise, Lesson
from apps.organizations.models import Organization


STREAK_MILESTONES = [
    {"days": 3, "multiplier": 1.1, "label": "3-Day Streak"},
    {"days": 7, "multiplier": 1.25, "label": "1-Week Streak"},
    {"days": 14, "multiplier": 1.5, "label": "2-Week Streak"},
    {"days": 30, "multiplier": 2.0, "label": "1-Month Streak"},
]


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
        # Upgraded to modern UniqueConstraint for stricter DB-level locking
        constraints = [
            models.UniqueConstraint(
                fields=["user", "badge"], name="unique_user_badge_award"
            )
        ]


class XPEvent(models.Model):
    """Tracks XP changes for a user from various source actions."""

    SOURCE_CHOICES = [
        ("lesson", "Lesson"),
        ("exercise", "Exercise"),
        ("pr", "Pull Request"),
        ("issue", "Issue"),
        ("review", "Review"),
        ("badge", "Badge"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="xp_events")
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    base_points = models.PositiveIntegerField()
    multiplier = models.FloatField(default=1.0)
    xp_delta = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "source_type"], name="idx_xp_user_source"),
            models.Index(fields=["-created_at"], name="idx_xp_created_desc"),
        ]

    def __str__(self):
        return f"XPEvent(user={self.user.username}, source={self.source_type}, delta={self.xp_delta})"


class LessonProgressSync(models.Model):
    """Idempotency ledger for lesson progress sync requests.

    Stores the result snapshot for a single (user, lesson, idempotency_key)
    so that client retries or out-of-order delivery do not re-apply the
    multiplier / side-effects.
    """

    objects = models.Manager()

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="lesson_progress_syncs",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="progress_syncs",
    )

    idempotency_key = models.CharField(max_length=255)

    # Snapshot of applied state
    completed = models.BooleanField(default=False)
    base_score = models.PositiveIntegerField(default=0)
    multiplier_applied = models.FloatField(default=1.0)
    score = models.PositiveIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1000),
        ],
    )

    client_timestamp_ms = models.BigIntegerField(null=True, blank=True)

    # When the server applied this sync item
    server_updated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson", "idempotency_key"],
                name="unique_user_lesson_sync_key",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "lesson"], name="idx_lp_sync_user_lesson"),
            models.Index(fields=["idempotency_key"], name="idx_lp_sync_key"),
        ]


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
    attempt_count = models.IntegerField(default=0)
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
    submitted_command = models.CharField(max_length=255, default="")
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
        max_length=64,
        unique=True,
        default=uuid.uuid4,
        db_index=True,
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
        PENDING_REVIEW = "pending_review", "Pending Review"
        REVIEWED = "reviewed", "Reviewed"
        ESCALATED = "escalated", "Escalated"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="code_submissions"
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name="submissions",
        null=True,
        blank=True,
    )
    assigned_reviewers = models.ManyToManyField(
        User, blank=True, related_name="assigned_reviews"
    )
    title = models.CharField(max_length=255)
    code_snippet = models.TextField()
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} by {self.user.username}"


class PlagiarismReport(models.Model):
    """Model to store plagiarism detection results for a code submission.

    Fields correspond to the migration that creates this table.
    """

    objects = models.Manager()
    submission = models.ForeignKey(
        CodeSubmission, on_delete=models.CASCADE, related_name="plagiarism_reports"
    )
    matched_submission = models.ForeignKey(
        CodeSubmission, on_delete=models.CASCADE, related_name="matched_in_reports"
    )
    similarity_score = models.FloatField()
    is_flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-similarity_score"]
        unique_together = ("submission", "matched_submission")

    def __str__(self):
        return f"PlagiarismReport(submission={self.submission.id}, matched={self.matched_submission.id}, score={self.similarity_score})"


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
    is_approved = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)
    points_earned = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("submission", "reviewer")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.submission.title}"


class StreakProfile(models.Model):
    """Tracks daily coding streaks for a user."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="streak_profile"
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def current_multiplier(self) -> float:
        from apps.progress.streak_engine import StreakEngine
        return StreakEngine.get_multiplier_for_streak(self.current_streak)

    @current_multiplier.setter
    def current_multiplier(self, value):
        pass

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "current_streak"], name="idx_streak_user_current"
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.current_streak} day streak"


class DailyActivity(models.Model):
    """Deterministic ledger of meaningful user activity on a local date."""

    class DoesNotExist(ObjectDoesNotExist):
        pass

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="daily_activities"
    )
    date = models.DateField()
    activity_type = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="unique_user_daily_activity"
            )
        ]
        indexes = [
            models.Index(fields=["user", "date"], name="idx_daily_activity_user_date"),
            models.Index(fields=["-date"], name="idx_daily_activity_date_desc"),
        ]

    def __str__(self):
        return f"DailyActivity(user={self.user_id}, date={self.date}, type={self.activity_type})"

    @classmethod
    def log_and_update_streak(
        cls, *, user: User, date, activity_type: str | None = None
    ):
        """Create a DailyActivity row for (user, date) if missing, then update streak.

        Returns (created: bool, streak_profile: StreakProfile).
        """
        from django.db import transaction

        # Ensure deterministic behavior under concurrency.
        with transaction.atomic():
            obj, created = cls.objects.get_or_create(
                user=user,
                date=date,
                defaults={"activity_type": activity_type},
            )

            streak_profile, _ = StreakProfile.objects.get_or_create(user=user)

            if created:
                yesterday = date - timezone.timedelta(days=1)
                yesterday_exists = cls.objects.filter(
                    user=user, date=yesterday
                ).exists()

                if yesterday_exists:
                    streak_profile.current_streak = streak_profile.current_streak + 1
                else:
                    streak_profile.current_streak = 1

                streak_profile.last_activity_date = date
                streak_profile.longest_streak = max(
                    streak_profile.longest_streak, streak_profile.current_streak
                )
                streak_profile.save(
                    update_fields=[
                        "current_streak",
                        "longest_streak",
                        "last_activity_date",
                        "updated_at",
                    ]
                )

            return created, streak_profile


class LessonBookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookmarks")
    lesson = models.ForeignKey(
        "content.Lesson", on_delete=models.CASCADE, related_name="bookmarks"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user", "lesson")]

    def __str__(self):
        return f"{self.user.username} - {self.lesson.slug}"
