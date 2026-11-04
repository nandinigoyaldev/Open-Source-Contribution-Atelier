# The Django field stubs in use type ``default=`` as a class, so every literal default is
# reported. The values are valid Django.
# pyright: reportArgumentType=false
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ExportJob(models.Model):
    """
    One export of one dataset for one user.

    The job row is the source of truth for the pipeline: ``checkpoint`` says how far the file has
    been written and verified, so a job interrupted by a worker restart carries on from there
    instead of starting again (see ``apps.data_exports.runner``).
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    STATUS_CHOICES = [
        (QUEUED, "Queued"),
        (RUNNING, "Running"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    ]
    FORMAT_CHOICES = [("csv", "CSV"), ("ndjson", "Newline-delimited JSON")]
    ACTIVE_STATUSES = (QUEUED, RUNNING)
    FINISHED_STATUSES = (COMPLETED, FAILED, CANCELLED, EXPIRED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_jobs"
    )
    dataset = models.CharField(max_length=50)
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="csv")
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=QUEUED, db_index=True
    )

    # Progress: how much of the file is written and safe to resume from.
    # {"last_pk": 1234, "rows": 1200, "bytes": 88211}
    checkpoint = models.JSONField(default=dict, blank=True)
    rows_written = models.PositiveBigIntegerField(default=0)
    bytes_written = models.PositiveBigIntegerField(default=0)
    # Rows the dataset had when the job was created; progress is an estimate against this.
    total_rows = models.PositiveBigIntegerField(null=True, blank=True)

    # Work ownership. A worker holds the job while ``lease_token`` is set and ``heartbeat_at``
    # is recent; every checkpoint is written only if the token still matches (fencing).
    lease_token = models.UUIDField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_run_at = models.DateTimeField(null=True, blank=True)
    cancel_requested = models.BooleanField(default=False)

    error = models.TextField(blank=True)
    file_name = models.CharField(max_length=120, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "heartbeat_at"], name="idx_exp_status_heartbeat"
            ),
            models.Index(fields=["user", "status"], name="idx_exp_user_status"),
            models.Index(
                fields=["status", "expires_at"], name="idx_exp_status_expires"
            ),
        ]

    def __str__(self):
        return f"Export {self.id} [{self.dataset}/{self.file_format}] {self.status}"

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_downloadable(self) -> bool:
        return (
            self.status == self.COMPLETED
            and bool(self.file_name)
            and (self.expires_at is None or self.expires_at > timezone.now())
        )
