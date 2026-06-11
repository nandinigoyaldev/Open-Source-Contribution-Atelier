from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0003_userbadge"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="lessonprogress",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="lessonprogress",
            constraint=models.UniqueConstraint(
                fields=["user", "lesson"],
                name="unique_user_lesson_progress",
            ),
        ),
        migrations.AddIndex(
            model_name="lessonprogress",
            index=models.Index(
                fields=["user", "completed"],
                name="idx_progress_user_completed",
            ),
        ),
        migrations.AddIndex(
            model_name="lessonprogress",
            index=models.Index(
                fields=["user", "score"],
                name="idx_progress_user_score",
            ),
        ),
    ]
