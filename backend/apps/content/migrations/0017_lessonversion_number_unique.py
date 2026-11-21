from django.db import migrations, models


class Migration(migrations.Migration):
    """Separate from 0016 so the backfill's UPDATEs are committed before the ALTERs."""

    dependencies = [
        ("content", "0016_lessonversion_workflow"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lessonversion",
            name="number",
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AddConstraint(
            model_name="lessonversion",
            constraint=models.UniqueConstraint(
                fields=("lesson", "number"), name="content_lessonversion_number"
            ),
        ),
    ]
