# Manually written to restore an operation that was accidentally dropped
# from migration history across two separate cleanup commits (54393ae and
# 6f31c16), even though apps/progress/models.py already assumes it happened:
# UserBadge was upgraded from a plain `unique_together` to a named
# `UniqueConstraint` ("unique_user_badge_award") for stricter DB-level
# locking. This restores that schema change so migration history matches
# the actual current model state.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0021_lessonbookmark"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="userbadge",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="userbadge",
            constraint=models.UniqueConstraint(
                fields=("user", "badge"), name="unique_user_badge_award"
            ),
        ),
    ]