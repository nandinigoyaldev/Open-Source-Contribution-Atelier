import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    # Also merges the two 0008 leaves (cursor index, weekly digest) into one history.
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0008_notification_cursor_index"),
        ("notifications", "0008_weekly_digest_delivery"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationOutbox",
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
                ("notif_type", models.CharField(max_length=50)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("source", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.CharField(max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("dispatched", "Dispatched to the delivery ledger"),
                            ("dead", "Dead-lettered"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                (
                    "next_attempt_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("locked_by", models.CharField(blank=True, max_length=64)),
                ("error_class", models.CharField(blank=True, max_length=20)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("dead_at", models.DateTimeField(blank=True, null=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_outbox",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="notificationoutbox",
            index=models.Index(
                fields=["status", "next_attempt_at"], name="idx_outbox_status_next"
            ),
        ),
        migrations.AddIndex(
            model_name="notificationoutbox",
            index=models.Index(
                fields=["status", "created_at"], name="idx_outbox_status_created"
            ),
        ),
        migrations.AddConstraint(
            model_name="notificationoutbox",
            constraint=models.UniqueConstraint(
                fields=["recipient", "idempotency_key"],
                name="uniq_outbox_recipient_key",
            ),
        ),
    ]
