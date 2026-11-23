from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0003_oidc_sso"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="slug",
            field=models.SlugField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="is_enterprise",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organization",
            name="schema_name",
            field=models.CharField(blank=True, max_length=63, null=True, unique=True),
        ),
    ]
