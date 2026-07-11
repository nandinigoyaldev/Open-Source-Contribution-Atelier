"""
Initial migration for cache app.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="CacheConfig",
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
                ("model_name", models.CharField(max_length=100, unique=True)),
                (
                    "strategy",
                    models.CharField(
                        choices=[
                            ("write_through", "Write-Through"),
                            ("write_around", "Write-Around"),
                            ("write_back", "Write-Back"),
                            ("stale_while_revalidate", "Stale-While-Revalidate"),
                        ],
                        default="write_through",
                        max_length=50,
                    ),
                ),
                ("ttl", models.IntegerField(default=300)),
                ("max_size", models.IntegerField(default=1000)),
                ("warm_on_startup", models.BooleanField(default=False)),
                ("warm_queries", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="CacheDependency",
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
                ("source_object_id", models.PositiveIntegerField()),
                ("target_object_id", models.PositiveIntegerField()),
                ("cache_key", models.CharField(db_index=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cache_source_dependencies",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "target_content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cache_target_dependencies",
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["source_content_type", "source_object_id"],
                        name="cache_cach_source__55ee05_idx",
                    ),
                    models.Index(
                        fields=["target_content_type", "target_object_id"],
                        name="cache_cach_target__44d37f_idx",
                    ),
                    models.Index(
                        fields=["cache_key"], name="cache_cach_cache_k_e42dcf_idx"
                    ),
                ],
                "unique_together": {
                    (
                        "source_content_type",
                        "source_object_id",
                        "target_content_type",
                        "target_object_id",
                        "cache_key",
                    )
                },
            },
        ),
    ]
