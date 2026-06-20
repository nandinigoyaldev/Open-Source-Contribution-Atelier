from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0008_merge_20260616_2344"),
    ]

    operations = [
        migrations.AddField(
            model_name="badge",
            name="category",
            field=models.CharField(default="general", max_length=100),
        ),
        migrations.AddField(
            model_name="badge",
            name="icon_asset_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
