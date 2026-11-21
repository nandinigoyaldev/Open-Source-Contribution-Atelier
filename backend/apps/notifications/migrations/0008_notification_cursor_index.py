from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0007_delivery_ledger")]

    operations = [
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "-created_at", "-id"],
                name="idx_notif_recipient_cursor",
            ),
        ),
    ]
