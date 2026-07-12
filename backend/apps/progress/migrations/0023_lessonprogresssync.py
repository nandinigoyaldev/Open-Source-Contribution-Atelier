from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("progress", "0022_dailyactivity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonProgressSync",
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
                ("idempotency_key", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_progress_syncs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_syncs",
                        to="content.lesson",
                    ),
                ),
                (
                    "completed",
                    models.BooleanField(default=False),
                ),
                ("base_score", models.PositiveIntegerField(default=0)),
                ("multiplier_applied", models.FloatField(default=1.0)),
                ("score", models.PositiveIntegerField(default=0)),
                ("client_timestamp_ms", models.BigIntegerField(null=True, blank=True)),
                ("server_updated_at", models.DateTimeField(null=True, blank=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["user", "lesson"], name="idx_lp_sync_user_lesson"
                    ),
                    models.Index(fields=["idempotency_key"], name="idx_lp_sync_key"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["user", "lesson", "idempotency_key"],
                        name="unique_user_lesson_sync_key",
                    )
                ],
            },
        ),
    ]
