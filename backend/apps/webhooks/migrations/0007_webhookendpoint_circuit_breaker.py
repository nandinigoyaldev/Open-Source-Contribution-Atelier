from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0006_webhookdelivery_dedupe_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookendpoint",
            name="health_status",
            field=models.CharField(
                choices=[
                    ("healthy", "Healthy"),
                    ("degraded", "Degraded"),
                    ("suspended", "Suspended"),
                ],
                default="healthy",
                help_text="Health status: healthy, degraded, or suspended.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="webhookendpoint",
            name="consecutive_failure_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Consecutive delivery failures across all events.",
            ),
        ),
        migrations.AddField(
            model_name="webhookendpoint",
            name="circuit_broken_until",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp until which the circuit breaker is tripped.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="webhookendpoint",
            name="last_failure_reason",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Reason for the most recent delivery failure.",
            ),
        ),
        migrations.AddField(
            model_name="webhookendpoint",
            name="failure_threshold",
            field=models.PositiveIntegerField(
                default=5,
                help_text="Consecutive delivery failures before tripping the circuit breaker.",
            ),
        ),
        migrations.AddField(
            model_name="webhookendpoint",
            name="cooldown_seconds",
            field=models.PositiveIntegerField(
                default=900,
                help_text="Duration in seconds before allowing probe delivery in half-open state.",
            ),
        ),
    ]
