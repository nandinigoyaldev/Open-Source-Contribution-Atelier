from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0001_initial"),
    ]

    operations = [
        # Add new status choices and retry tracking fields to WebhookDelivery
        migrations.AddField(
            model_name="webhookdelivery",
            name="attempt_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Number of delivery attempts made so far.",
            ),
        ),
        migrations.AddField(
            model_name="webhookdelivery",
            name="next_retry_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When the next retry should be attempted.",
            ),
        ),
        migrations.AlterField(
            model_name="webhookdelivery",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("retrying", "Retrying"),
                    ("dead", "Dead"),
                ],
                default="pending",
                max_length=32,
            ),
        ),
        # Create the DeadLetterWebhook model
        migrations.CreateModel(
            name="DeadLetterWebhook",
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
                    "delivery",
                    models.OneToOneField(
                        help_text="The original delivery that exhausted all retries.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dead_letter",
                        to="webhooks.webhookdelivery",
                    ),
                ),
                (
                    "reason",
                    models.TextField(
                        help_text="The final error or non-2xx status that caused permanent failure."
                    ),
                ),
                (
                    "replayed",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this entry has been manually requeued for replay.",
                    ),
                ),
                (
                    "replayed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="Timestamp of the most recent replay attempt.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
