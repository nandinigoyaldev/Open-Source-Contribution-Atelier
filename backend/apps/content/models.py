from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = get_user_model()


class Lesson(models.Model):
    class DoesNotExist(ObjectDoesNotExist):
        pass

    objects = models.Manager()

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

    class Meta:
        ordering = ["order", "id"]


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
    def delete(self, hard=False):
        if hard:
            return super().delete()  # type: ignore
        return self.update(is_deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


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
