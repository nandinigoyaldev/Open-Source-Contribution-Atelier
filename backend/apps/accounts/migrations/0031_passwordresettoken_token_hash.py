from django.db import migrations, models


def delete_reset_tokens(apps, schema_editor):
    """
    Old rows hold the raw token, and a reset token lives for 15 minutes at most,
    so they are dropped instead of converted. Links already sent stop working.
    """
    apps.get_model("accounts", "PasswordResetToken").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0030_webauthncredential"),
    ]

    operations = [
        migrations.RunPython(delete_reset_tokens, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="passwordresettoken",
            name="token",
        ),
        migrations.AddField(
            model_name="passwordresettoken",
            name="token_hash",
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        # Going back re-adds a unique column, which only works on an empty table.
        migrations.RunPython(migrations.RunPython.noop, delete_reset_tokens),
    ]
