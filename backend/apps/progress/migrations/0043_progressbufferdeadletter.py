import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("progress", "0042_lessonprogress_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProgressBufferDeadLetter",
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
                    "activity_type",
                    models.CharField(db_index=True, default="lesson", max_length=64),
                ),
                ("source_id", models.CharField(db_index=True, max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("replayed", "Replayed"),
                            ("discarded", "Discarded"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("replayed", models.BooleanField(default=False)),
                ("replayed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "replayed_by",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_dead_letters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Progress Buffer Dead Letter",
                "verbose_name_plural": "Progress Buffer Dead Letters",
                "ordering": ["-created_at"],
            },
        ),
    ]
