from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = False
    dependencies = [
        ("progress", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="quizattempt",
            name="client_attempt_id",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterUniqueTogether(
            name="quizattempt",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="quizattempt",
            constraint=models.UniqueConstraint(
                fields=("user", "client_attempt_id"),
                name="unique_quizattempt_user_client_attempt_id",
            ),
        ),
        migrations.AddIndex(
            model_name="quizattempt",
            index=models.Index(
                fields=["user", "client_attempt_id"], name="idx_quiz_client_attempt"
            ),
        ),
    ]
