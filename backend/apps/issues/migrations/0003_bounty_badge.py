# Generated migration for adding badge field to Bounty model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("issues", "0002_bounty"),
        ("progress", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bounty",
            name="badge",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional badge awarded upon completion of this bounty.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bounties",
                to="progress.badge",
            ),
        ),
    ]
