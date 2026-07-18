from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_alter_userprofile_timezone"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "auth_user_username_ci_unique "
                "ON auth_user (LOWER(username));"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS auth_user_username_ci_unique;"
            ),
        ),
    ]
