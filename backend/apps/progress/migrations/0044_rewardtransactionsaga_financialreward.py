import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("progress", "0043_progressbufferdeadletter"),
    ]

    operations = [
        migrations.CreateModel(
            name="RewardTransactionSaga",
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
                    "saga_id",
                    models.CharField(db_index=True, max_length=64, unique=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PREPARING", "Preparing"),
                            ("COMMITTED", "Committed"),
                            ("COMPENSATING", "Compensating"),
                            ("ABORTED", "Aborted"),
                        ],
                        db_index=True,
                        default="PREPARING",
                        max_length=20,
                    ),
                ),
                (
                    "action_type",
                    models.CharField(default="batch_reward_allocation", max_length=100),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("step_states", models.JSONField(blank=True, default=list)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reward_sagas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="FinancialReward",
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
                    "saga_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=64
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="USD", max_length=10)),
                (
                    "source_type",
                    models.CharField(default="challenge_reward", max_length=50),
                ),
                (
                    "source_id",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("allocated", "Allocated"),
                            ("revoked", "Revoked"),
                            ("refunded", "Refunded"),
                        ],
                        db_index=True,
                        default="allocated",
                        max_length=20,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="financial_rewards",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="rewardtransactionsaga",
            index=models.Index(
                fields=["user", "status"], name="idx_reward_saga_user_status"
            ),
        ),
        migrations.AddIndex(
            model_name="rewardtransactionsaga",
            index=models.Index(
                fields=["status", "-created_at"],
                name="idx_reward_saga_status_created",
            ),
        ),
        migrations.AddIndex(
            model_name="financialreward",
            index=models.Index(
                fields=["user", "status"], name="idx_fin_reward_user_status"
            ),
        ),
        migrations.AddIndex(
            model_name="financialreward",
            index=models.Index(fields=["saga_id"], name="idx_fin_reward_saga_id"),
        ),
    ]
