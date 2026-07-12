# Generated manually — adds description, tags, and content_type_name to SearchDocument

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("search", "0003_searchanalytics"),
    ]

    operations = [
        # Add description field (weight 'B' in tsvector)
        migrations.AddField(
            model_name="searchdocument",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        # Add tags field (weight 'B' in tsvector — e.g. category, difficulty, status)
        migrations.AddField(
            model_name="searchdocument",
            name="tags",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        # Denormalized content type name for O(1) API-level filtering
        migrations.AddField(
            model_name="searchdocument",
            name="content_type_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
