"""
Migration to add jwt_token_version to UserProfile.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_userprofile_bio'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='jwt_token_version',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='last_password_change',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]