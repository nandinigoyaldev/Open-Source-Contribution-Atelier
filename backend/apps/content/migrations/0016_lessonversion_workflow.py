import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_revisions(apps, schema_editor):
    """
    Number the existing snapshots per lesson (oldest = v1).

    Before the workflow every snapshot was taken from the live lesson, so they
    all count as published history: each is archived with published_at set to
    when it was taken, and the newest one that still matches the lesson's
    content becomes the published revision.
    """
    Lesson = apps.get_model("content", "Lesson")
    LessonVersion = apps.get_model("content", "LessonVersion")

    batch = []
    lesson_id, number = None, 0
    for version in LessonVersion.objects.order_by(
        "lesson_id", "created_at", "id"
    ).iterator():
        if version.lesson_id != lesson_id:
            lesson_id, number = version.lesson_id, 0
        number += 1
        version.number = number
        version.status = "archived"
        version.published_at = version.created_at
        batch.append(version)
        if len(batch) >= 500:
            LessonVersion.objects.bulk_update(
                batch, ["number", "status", "published_at"]
            )
            batch = []
    if batch:
        LessonVersion.objects.bulk_update(batch, ["number", "status", "published_at"])

    for lesson in Lesson.objects.only("id", "content").iterator():
        live = (
            LessonVersion.objects.filter(lesson_id=lesson.id, content=lesson.content)
            .order_by("-number")
            .values_list("id", flat=True)
            .first()
        )
        if live is not None:
            LessonVersion.objects.filter(pk=live).update(status="published")


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0015_curriculum_import"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="lessonversion",
            options={"ordering": ["-number"]},
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="number",
            # Filled in below, made non-null in 0017.
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("review", "In review"),
                    ("published", "Published"),
                    ("archived", "Archived"),
                ],
                db_index=True,
                default="draft",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="note",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="authored_lesson_revisions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="restored_from",
            field=models.ForeignKey(
                blank=True,
                help_text="The earlier revision a rollback copied.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="restorations",
                to="content.lessonversion",
            ),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lessonversion",
            name="published_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="published_lesson_revisions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_revisions, migrations.RunPython.noop),
    ]
