import django.contrib.postgres.indexes
import django.contrib.postgres.operations
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("search", "0001_initial"),
    ]

    operations = [
        django.contrib.postgres.operations.TrigramExtension(),
        migrations.AddIndex(
            model_name="searchdocument",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["title"],
                name="trigram_title_gin_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
