import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("content", "0017_lessonversion_number_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="CurriculumReleaseManifest",
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
                ("curriculum_slug", models.SlugField(db_index=True, max_length=255)),
                ("version", models.CharField(max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("validated", "Validated"),
                            ("active", "Active"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "manifest_data",
                    models.JSONField(
                        default=dict,
                        help_text="Items list referencing lesson slugs, immutable revision numbers, order, and prerequisite DAG.",
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="curriculum_releases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "unique_together": {("curriculum_slug", "version")},
            },
        ),
        migrations.CreateModel(
            name="CurriculumEnrollment",
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
                ("curriculum_slug", models.SlugField(db_index=True, max_length=255)),
                ("enrolled_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "current_release",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="enrolled_learners",
                        to="content.curriculumreleasemanifest",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="curriculum_enrollments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-enrolled_at"],
                "unique_together": {("user", "curriculum_slug")},
            },
        ),
        migrations.CreateModel(
            name="CurriculumMigrationAudit",
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
                ("retained_completions", models.JSONField(default=list)),
                ("newly_required_prerequisites", models.JSONField(default=list)),
                ("removed_lessons", models.JSONField(default=list)),
                ("unresolved_mappings", models.JSONField(default=list)),
                ("is_rollback", models.BooleanField(default=False)),
                ("migrated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_curriculum_migrations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="migration_history",
                        to="content.curriculumenrollment",
                    ),
                ),
                (
                    "source_release",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="source_migrations",
                        to="content.curriculumreleasemanifest",
                    ),
                ),
                (
                    "target_release",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="target_migrations",
                        to="content.curriculumreleasemanifest",
                    ),
                ),
            ],
            options={
                "ordering": ["-migrated_at"],
            },
        ),
    ]
