from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0041_progress_query_indexes"),
    ]

    operations = [
        # db_default on a plain integer column: PostgreSQL 11+ adds this without
        # rewriting or scanning the table, and rows inserted by old code during a
        # rolling deploy still get a version.
        migrations.AddField(
            model_name="lessonprogress",
            name="version",
            field=models.IntegerField(
                db_default=1,  # pyright: ignore[reportArgumentType]
                editable=False,
            ),
        ),
    ]
