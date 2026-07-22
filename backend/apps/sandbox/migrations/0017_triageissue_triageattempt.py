import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sandbox", "0016_conflictscenario_conflictattempt"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TriageIssue",
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
                    "title",
                    models.CharField(
                        help_text="Scenario title shown to the user.", max_length=255
                    ),
                ),
                (
                    "raw_issue_title",
                    models.CharField(
                        help_text="The poorly written title of the simulated issue.",
                        max_length=255,
                    ),
                ),
                (
                    "raw_issue_body",
                    models.TextField(
                        help_text="The poorly written body of the simulated issue (missing steps, no env, etc.)."
                    ),
                ),
                (
                    "correct_labels",
                    models.JSONField(
                        help_text='List of correct label strings, e.g. ["bug", "needs-repro"]'
                    ),
                ),
                (
                    "model_response",
                    models.TextField(
                        help_text="An exemplary maintainer response asking for missing info."
                    ),
                ),
                (
                    "hint",
                    models.TextField(
                        blank=True, help_text="Optional hint for the user."
                    ),
                ),
                (
                    "difficulty",
                    models.CharField(
                        choices=[
                            ("easy", "Easy"),
                            ("medium", "Medium"),
                            ("hard", "Hard"),
                        ],
                        default="medium",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["difficulty", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TriageAttempt",
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
                    "submitted_labels",
                    models.JSONField(
                        help_text='Labels the user chose, e.g. ["bug", "needs-repro"]'
                    ),
                ),
                (
                    "submitted_response",
                    models.TextField(
                        help_text="The response text the user wrote to the issue author."
                    ),
                ),
                (
                    "label_score",
                    models.IntegerField(
                        default=0, help_text="Score for label accuracy (0-50)."
                    ),
                ),
                (
                    "response_score",
                    models.IntegerField(
                        default=0, help_text="Score for response quality (0-50)."
                    ),
                ),
                (
                    "total_score",
                    models.IntegerField(default=0, help_text="Combined score (0-100)."),
                ),
                (
                    "passed",
                    models.BooleanField(
                        default=False, help_text="True if total_score >= 70."
                    ),
                ),
                (
                    "feedback",
                    models.TextField(
                        blank=True,
                        help_text="Automated feedback explaining the score.",
                    ),
                ),
                (
                    "badge_awarded",
                    models.CharField(
                        blank=True,
                        help_text='Badge slug awarded on pass, e.g. "triager".',
                        max_length=50,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "issue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="sandbox.triageissue",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="triage_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
