# Generated migration for LessonFeedback model

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("content", "0007_lessonthread_lessoncomment_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonFeedback",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        help_text="Star rating from 1 to 5",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                (
                    "comment",
                    models.TextField(blank=True, help_text="Optional written feedback"),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feedbacks",
                        to="content.lesson",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_feedbacks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("user", "lesson")},
            },
        ),
        migrations.AddIndex(
            model_name="lessonfeedback",
            index=models.Index(
                fields=["lesson", "is_deleted"],
                name="idx_feedback_les_del",
            ),
        ),
        migrations.AddIndex(
            model_name="lessonfeedback",
            index=models.Index(fields=["user", "lesson"], name="idx_feedback_user_les"),
        ),
    ]
