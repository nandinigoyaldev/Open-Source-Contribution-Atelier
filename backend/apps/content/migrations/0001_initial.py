from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Lesson",
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
                ("difficulty", models.CharField(max_length=32)),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(unique=True)),
                ("summary", models.TextField()),
                ("content", models.TextField()),
                ("estimated_minutes", models.PositiveIntegerField(default=15)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.CreateModel(
            name="Exercise",
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
                ("title", models.CharField(max_length=255)),
                ("prompt", models.TextField()),
                ("expected_command", models.CharField(max_length=255)),
                ("explanation", models.TextField(blank=True)),
                ("points", models.PositiveIntegerField(default=10)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="exercises",
                        to="content.lesson",
                    ),
                ),
            ],
        ),
    ]
