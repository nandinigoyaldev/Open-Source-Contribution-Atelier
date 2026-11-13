from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import AuditableModel, SoftDeleteModel
from apps.search.mixins import SearchIndexMixin

User = get_user_model()


class Lesson(AuditableModel, SearchIndexMixin):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True, blank=True
    )
    difficulty = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    content = models.TextField()
    learning_objectives = models.JSONField(default=list, blank=True)
    tips = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=100, default="general")
    estimated_minutes = models.PositiveIntegerField(
        default=15,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(120),
        ],
    )
    order = models.PositiveIntegerField(default=0)
    embedding = models.JSONField(
        null=True, blank=True, help_text="Pre-computed semantic embedding vector"
    )
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, related_name="dependents", blank=True
    )
    js_exercise = models.JSONField(null=True, blank=True, default=None)

    @property
    def reading_time(self) -> int:
        from .utils import calculate_reading_time

        return calculate_reading_time(self.content)

    class Meta:
        ordering = ["order", "id"]


class LessonVersion(models.Model):
    lesson = models.ForeignKey(
        Lesson, related_name="versions", on_delete=models.CASCADE
    )
    content = models.TextField()
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Exercise(models.Model):
    objects = models.Manager()
    lesson = models.ForeignKey(
        Lesson, related_name="exercises", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)
    prompt = models.TextField()
    expected_command = models.CharField(max_length=255)
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=10)


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs) -> tuple[int, dict[str, int]]:
        # Soft delete by default; restore by toggling `is_deleted`.
        self.update(is_deleted=True)
        return (1, {self.model._meta.label: 1})


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def delete(self):
        return self.get_queryset().delete()


class LessonThread(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="lesson_threads"
    )
    lesson = models.ForeignKey(
        "Lesson", on_delete=models.CASCADE, related_name="threads"
    )
    title = models.CharField(max_length=255)
    content = models.TextField(help_text="Markdown body for the thread")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["lesson", "is_deleted"],
                name="idx_lessonthread_les_del",
            ),
        ]

    def delete(self, using=None, keep_parents=False, hard=False):
        # Soft delete by default; restore by toggling `is_deleted`.
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)  # type: ignore
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
        return (1, {self._meta.label: 1})  # type: ignore

    def restore(self):
        self.is_deleted = False
        self.save(update_fields=["is_deleted"])

    def __str__(self):
        return f"Thread by {self.user.username}"  # type: ignore


class LessonComment(models.Model):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="lesson_comments"
    )
    thread = models.ForeignKey(
        "LessonThread", on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField(help_text="Markdown body for the comment")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["thread", "is_deleted"],
                name="idx_lessoncomment_thr_del",
            ),
        ]

    def delete(self, using=None, keep_parents=False, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)  # type: ignore
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
        return (1, {self._meta.label: 1})  # type: ignore

    def restore(self):
        self.is_deleted = False
        self.save(update_fields=["is_deleted"])

    def __str__(self):
        return f"Comment by {self.user.username}"  # type: ignore


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="comments", null=True, blank=True
    )
    content = models.TextField(help_text="The main body of the comment")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_deleted"], name="idx_comment_is_deleted"),
        ]

    def delete(self, using=None, keep_parents=False, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)  # type: ignore
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
        return (1, {self._meta.label: 1})  # type: ignore

    def restore(self):
        self.is_deleted = False
        self.save(update_fields=["is_deleted"])

    def __str__(self):
        status = "[DELETED] " if self.is_deleted else ""
        return f"{status}Comment by {self.user.username}"  # type: ignore


class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True, help_text="URL to the organization's logo")
    date_added = models.DateTimeField(auto_now_add=True)
    popularity_score = models.IntegerField(
        default=0, help_text="Higher score means more popular"
    )  # type: ignore

    class Meta:
        ordering = ["-popularity_score"]

    def __str__(self) -> str:
        return str(self.name)


class LessonFeedback(models.Model):
    """Stores user feedback for lessons including star ratings and optional comments."""

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="lesson_feedbacks"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="feedbacks"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
        help_text="Star rating from 1 to 5",
    )
    comment = models.TextField(blank=True, help_text="Optional written feedback")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["user", "lesson"]
        indexes = [
            models.Index(fields=["lesson", "is_deleted"], name="idx_feedback_les_del"),
            models.Index(fields=["user", "lesson"], name="idx_feedback_user_les"),
        ]

    def delete(self, using=None, keep_parents=False, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
        return (1, {self._meta.label: 1})

    def restore(self):
        self.is_deleted = False
        self.save(update_fields=["is_deleted"])

    def __str__(self):
        status = "[DELETED] " if self.is_deleted else ""
        return f"{status}Feedback by {self.user.username} for {self.lesson.title}: {self.rating} stars"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(
        max_length=160,
        blank=True,
        default="",
        help_text="A short biography or description.",
    )
    github_link = models.URLField(
        blank=True, default="", help_text="GitHub profile URL"
    )
    linkedin_link = models.URLField(
        blank=True, default="", help_text="LinkedIn profile URL"
    )
    portfolio_link = models.URLField(
        blank=True, default="", help_text="Personal portfolio URL"
    )

    def __str__(self):
        return f"Profile for {self.user.username}"


class ModuleDraft(SoftDeleteModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


Module = ModuleDraft


class LessonDraft(SoftDeleteModel):
    module = models.ForeignKey(
        ModuleDraft,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True)
    difficulty = models.CharField(max_length=32, default="beginner")
    tags = models.JSONField(default=list, blank=True)
    estimated_minutes = models.PositiveIntegerField(default=15)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    learning_objectives = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class QuizDraft(models.Model):
    lesson = models.ForeignKey(
        LessonDraft,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )
    question = models.TextField()
    options = models.JSONField(default=list)
    answer = models.IntegerField(default=0)
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Quiz question for {self.lesson.title}"


class LearningPath(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    required_roles = models.ManyToManyField(
        "rbac.Role",
        related_name="learning_paths",
        blank=True,
        help_text="Roles required to access this learning path. If empty, public to all authenticated users.",
    )
    lessons = models.ManyToManyField(Lesson, related_name="learning_paths", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def has_access(self, user) -> bool:
        if not self.required_roles.exists():
            return True
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        user_role_ids = user.user_roles.values_list("role_id", flat=True)
        return self.required_roles.filter(id__in=user_role_ids).exists()


class CurriculumImport(models.Model):
    """One bulk curriculum import: an uploaded archive and its progress.

    The row is the single source of truth for a run: ``status`` is the state
    machine, ``cursor`` is the index of the next lesson to validate (so a
    crashed worker resumes instead of starting over) and ``report`` holds the
    problems and the publish plan/result.
    """

    VALIDATING = "validating"
    PREVIEWED = "previewed"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    STATUS_CHOICES = [
        (VALIDATING, "Validating"),
        (PREVIEWED, "Previewed"),
        (PUBLISHING, "Publishing"),
        (PUBLISHED, "Published"),
        (FAILED, "Failed"),
    ]

    archive = models.FileField(upload_to="curriculum_imports/")
    original_name = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=VALIDATING, db_index=True
    )
    cursor = models.PositiveIntegerField(
        default=0, help_text="Index of the next lesson to validate"
    )
    total_lessons = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="curriculum_imports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"Curriculum import #{self.pk} ({self.status})"
