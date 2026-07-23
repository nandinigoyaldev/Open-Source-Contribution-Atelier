import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RepoHealthScore",
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
                    "repo_url",
                    models.URLField(
                        unique=True,
                        help_text="The GitHub repository URL (e.g., https://github.com/django/django).",
                    ),
                ),
                ("repo_owner", models.CharField(max_length=255)),
                ("repo_name", models.CharField(max_length=255)),
                ("open_issues", models.IntegerField(default=0)),
                ("closed_issues", models.IntegerField(default=0)),
                ("open_prs", models.IntegerField(default=0)),
                ("closed_prs", models.IntegerField(default=0)),
                (
                    "avg_pr_close_days",
                    models.FloatField(
                        blank=True,
                        help_text="Average number of days it takes to merge/close a PR.",
                        null=True,
                    ),
                ),
                ("contributor_count", models.IntegerField(default=0)),
                (
                    "last_commit_days_ago",
                    models.IntegerField(
                        blank=True,
                        help_text="Days since the last commit to the default branch.",
                        null=True,
                    ),
                ),
                (
                    "sentiment_score",
                    models.FloatField(
                        blank=True,
                        help_text="Aggregated polarity score of recent PR comments (-1.0 to 1.0).",
                        null=True,
                    ),
                ),
                (
                    "sentiment_label",
                    models.CharField(
                        blank=True,
                        help_text="Human-readable label: 'positive', 'neutral', or 'negative'.",
                        max_length=20,
                    ),
                ),
                (
                    "health_score",
                    models.IntegerField(
                        default=0,
                        help_text="Overall computed health score out of 100.",
                    ),
                ),
                (
                    "red_flags",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="List of warning strings for the user.",
                    ),
                ),
                (
                    "green_flags",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="List of positive strings for the user.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "analyzed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="repo_health_analyses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
    ]
