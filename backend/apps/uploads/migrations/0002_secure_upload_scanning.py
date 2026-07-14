from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("uploads", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="uploadsession",
            name="upload_type",
            field=models.CharField(
                choices=[("avatar", "Avatar"), ("project", "Project file"), ("lesson", "Lesson asset")],
                default="project",
                max_length=20,
            ),
        ),
        migrations.AddField(model_name="uploadsession", name="detected_mime_type", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="uploadsession", name="quarantine_path", field=models.CharField(blank=True, max_length=512)),
        migrations.AddField(model_name="uploadsession", name="scan_message", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="uploadsession", name="scan_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="uploadsession", name="scan_completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(
            model_name="uploadsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"), ("uploading", "Uploading"),
                    ("quarantined", "Quarantined"), ("scanning", "Scanning"),
                    ("clean", "Clean"), ("infected", "Infected"),
                    ("rejected", "Rejected"), ("released", "Released by administrator"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="UploadScanHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("result", models.CharField(choices=[("clean", "Clean"), ("infected", "Infected"), ("error", "Scanner error"), ("released", "Released by administrator")], max_length=20)),
                ("engine", models.CharField(default="ClamAV", max_length=100)),
                ("signature", models.CharField(blank=True, max_length=255)),
                ("message", models.TextField(blank=True)),
                ("scanned_at", models.DateTimeField(auto_now_add=True)),
                ("released_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("upload", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scan_history", to="uploads.uploadsession")),
            ],
            options={"ordering": ["-scanned_at"]},
        ),
    ]
