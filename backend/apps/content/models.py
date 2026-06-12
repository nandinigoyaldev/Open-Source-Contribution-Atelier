from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Lesson(models.Model):
    difficulty = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    content = models.TextField()
    learning_objectives = models.JSONField(default=list, blank=True)
    tips = models.JSONField(default=list, blank=True)
    estimated_minutes = models.PositiveIntegerField(
    default=15,
    validators=[
        MinValueValidator(1),
        MaxValueValidator(120),
    ],
)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class Exercise(models.Model):
    lesson = models.ForeignKey(Lesson, related_name="exercises", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    prompt = models.TextField()
    expected_command = models.CharField(max_length=255)
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=10)

