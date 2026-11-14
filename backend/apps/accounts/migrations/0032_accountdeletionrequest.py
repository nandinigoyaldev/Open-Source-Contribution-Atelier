import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0031_passwordresettoken_token_hash"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountDeletionRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("cancelled", "Cancelled"),
                            ("completed", "Completed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("scheduled_for", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account_deletion_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "accounts_accountdeletionrequest",
                "ordering": ["-requested_at"],
            },
        ),
    ]
