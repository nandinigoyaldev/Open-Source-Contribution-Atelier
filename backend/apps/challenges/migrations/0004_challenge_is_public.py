from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0003_challengeoftheday_challengecompletion"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="is_public",
            field=models.BooleanField(default=True),
        ),
    ]
