from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_rename_notificatio_recipie_4e3567_idx_idx_recipientis_read"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationChannelPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notif_type", models.CharField(max_length=20)),
                ("channel_id", models.CharField(max_length=50)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.user")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "notif_type", "channel_id"], name="idx_notif_chan_pref"),
                ],
                "unique_together": {("user", "notif_type", "channel_id")},
            },
        ),
        migrations.CreateModel(
            name="NotificationDeadLetter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel_id", models.CharField(max_length=50)),
                ("error", models.TextField()),
                ("payload_snapshot", models.JSONField(blank=True, default=dict)),
                ("failed_at", models.DateTimeField(auto_now_add=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dead_letters", to="notifications.notification")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_dead_letters", to="accounts.user")),
            ],
            options={
                "indexes": [models.Index(fields=["recipient", "channel_id"], name="idx_dead_letter")],
            },
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel_id", models.CharField(max_length=50)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("bounced", "Bounced"), ("opened", "Opened"), ("clicked", "Clicked")], default="pending", max_length=20)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("next_retry_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="notifications.notification")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_deliveries", to="accounts.user")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["recipient", "channel_id", "status"], name="idx_delivery_rl"),
                    models.Index(fields=["notification", "channel_id"], name="idx_delivery_notif_chan"),
                ],
            },
        ),
    ]

