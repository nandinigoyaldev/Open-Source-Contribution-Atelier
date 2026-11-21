import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_secret():
    return secrets.token_hex(32)


class WebhookEndpoint(models.Model):
    HEALTH_STATUS_HEALTHY = "healthy"
    HEALTH_STATUS_DEGRADED = "degraded"
    HEALTH_STATUS_SUSPENDED = "suspended"
    HEALTH_STATUS_CHOICES = [
        (HEALTH_STATUS_HEALTHY, "Healthy"),
        (HEALTH_STATUS_DEGRADED, "Degraded"),
        (HEALTH_STATUS_SUSPENDED, "Suspended"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webhooks",
        help_text="The user or organization that owns this webhook.",
    )
    target_url = models.URLField(
        max_length=512, help_text="The endpoint URL where webhook events will be sent."
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this webhook is currently enabled."
    )
    events = models.JSONField(
        default=list,
        help_text="A list of event types this webhook is subscribed to (e.g. ['lesson.completed', 'user.signup']).",
    )
    encrypted_secret = models.TextField(
        null=True,
        blank=True,
        help_text="Encrypted shared secret used to sign the webhook payloads.",
    )
    encrypted_old_secret = models.TextField(
        null=True,
        blank=True,
        help_text="Encrypted previous shared secret (for rotation grace period).",
    )
    old_secret_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration timestamp for the old secret.",
    )
    health_status = models.CharField(
        max_length=32,
        choices=HEALTH_STATUS_CHOICES,
        default=HEALTH_STATUS_HEALTHY,
        help_text="Health status: healthy, degraded, or suspended.",
    )
    consecutive_failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive delivery failures across all events.",
    )
    circuit_broken_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp until which the circuit breaker is tripped.",
    )
    last_failure_reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason for the most recent delivery failure.",
    )
    failure_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Consecutive delivery failures before tripping the circuit breaker.",
    )
    cooldown_seconds = models.PositiveIntegerField(
        default=900,
        help_text="Duration in seconds before allowing probe delivery in half-open state.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_circuit_open(self) -> bool:
        """Returns True if circuit is open (deliveries should fast-fail)."""
        if not self.is_active:
            return True
        if self.health_status == self.HEALTH_STATUS_SUSPENDED:
            return True
        if self.circuit_broken_until and timezone.now() < self.circuit_broken_until:
            return True
        return False

    def is_half_open(self) -> bool:
        """Returns True if cooldown has elapsed and a canary probe is permitted."""
        if (
            self.health_status == self.HEALTH_STATUS_DEGRADED
            and self.circuit_broken_until
        ):
            return timezone.now() >= self.circuit_broken_until
        return False

    @property
    def circuit_state(self) -> str:
        """Returns standard circuit-breaker state representation: CLOSED, OPEN, HALF_OPEN, or SUSPENDED."""
        if not self.is_active or self.health_status == self.HEALTH_STATUS_SUSPENDED:
            return "SUSPENDED"
        if self.health_status == self.HEALTH_STATUS_DEGRADED:
            return "HALF_OPEN" if self.is_half_open() else "OPEN"
        return "CLOSED"

    def record_success(self) -> None:
        """Resets failure counts and restores healthy state on successful delivery."""
        if (
            self.consecutive_failure_count > 0
            or self.health_status != self.HEALTH_STATUS_HEALTHY
            or self.circuit_broken_until is not None
        ):
            self.consecutive_failure_count = 0
            self.circuit_broken_until = None
            self.health_status = self.HEALTH_STATUS_HEALTHY
            self.last_failure_reason = ""
            self.save(
                update_fields=[
                    "consecutive_failure_count",
                    "circuit_broken_until",
                    "health_status",
                    "last_failure_reason",
                    "updated_at",
                ]
            )

    def record_failure(self, reason: str) -> None:
        """Increments consecutive failures and trips circuit if threshold exceeded."""
        self.consecutive_failure_count += 1
        self.last_failure_reason = str(reason)[:1000]
        now = timezone.now()

        if self.consecutive_failure_count >= self.failure_threshold:
            multiplier = max(
                1, self.consecutive_failure_count - self.failure_threshold + 1
            )
            cooldown = self.cooldown_seconds * multiplier
            if self.consecutive_failure_count >= self.failure_threshold * 3:
                self.health_status = self.HEALTH_STATUS_SUSPENDED
                self.circuit_broken_until = now + timezone.timedelta(days=7)
            else:
                self.health_status = self.HEALTH_STATUS_DEGRADED
                self.circuit_broken_until = now + timezone.timedelta(seconds=cooldown)

        self.save(
            update_fields=[
                "consecutive_failure_count",
                "circuit_broken_until",
                "health_status",
                "last_failure_reason",
                "updated_at",
            ]
        )

    def reset_circuit(self) -> None:
        """Manually resets circuit breaker to healthy state."""
        self.consecutive_failure_count = 0
        self.circuit_broken_until = None
        self.health_status = self.HEALTH_STATUS_HEALTHY
        self.last_failure_reason = ""
        self.save(
            update_fields=[
                "consecutive_failure_count",
                "circuit_broken_until",
                "health_status",
                "last_failure_reason",
                "updated_at",
            ]
        )

    @property
    def secret(self):
        # 1. Return decrypted active secret if present
        if self.encrypted_secret:
            from apps.cache.audit_logger import AuditLogger

            AuditLogger.log(
                user_id=str(self.user.id) if self.user else "system",
                action="secret_accessed",
                resource="webhook_endpoint",
                resource_id=str(self.id) if self.id else None,
                method="GET",
                ip_address="127.0.0.1",
                status_code=200,
            )
            from .security import decrypt_secret

            return decrypt_secret(self.encrypted_secret)

        # 2. Fall back to legacy plaintext secret_plain if present in database (for transition/migration)
        if hasattr(self, "secret_plain") and self.secret_plain:
            from apps.cache.audit_logger import AuditLogger

            AuditLogger.log(
                user_id=str(self.user.id) if self.user else "system",
                action="secret_accessed",
                resource="webhook_endpoint",
                resource_id=str(self.id) if self.id else None,
                method="GET",
                ip_address="127.0.0.1",
                status_code=200,
            )
            return self.secret_plain

        return None

    @secret.setter
    def secret(self, value):
        if value:
            from .security import encrypt_secret

            self.encrypted_secret = encrypt_secret(value)
            self._raw_secret = value
            if hasattr(self, "secret_plain"):
                self.secret_plain = None
        else:
            self.encrypted_secret = None
            self._raw_secret = None
            if hasattr(self, "secret_plain"):
                self.secret_plain = None

    def get_valid_secrets(self) -> list[str]:
        valid_list = []
        active_sec = self.secret
        if active_sec:
            valid_list.append(active_sec)

        if self.encrypted_old_secret and self.old_secret_expires_at:
            if timezone.now() < self.old_secret_expires_at:
                from .security import decrypt_secret

                old_sec = decrypt_secret(self.encrypted_old_secret)
                if old_sec:
                    valid_list.append(old_sec)

        return valid_list

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # If no active secret is set (neither encrypted nor plain)
        if not self.encrypted_secret and (
            not hasattr(self, "secret_plain") or not self.secret_plain
        ):
            raw_val = generate_secret()
            from .security import encrypt_secret

            self.encrypted_secret = encrypt_secret(raw_val)
            self._raw_secret = raw_val
            if hasattr(self, "secret_plain"):
                self.secret_plain = None

            # Log secret creation
            from apps.cache.audit_logger import AuditLogger

            AuditLogger.log(
                user_id=str(self.user.id) if self.user else "system",
                action="secret_created",
                resource="webhook_endpoint",
                resource_id=None,
                method="CREATE",
                ip_address="127.0.0.1",
                status_code=201,
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.target_url} ({self.user.username})"

    objects = models.Manager()


class WebhookDelivery(models.Model):
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    event_type = models.CharField(max_length=128)
    payload = models.JSONField()
    status = models.CharField(
        max_length=32,
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("retrying", "Retrying"),
            ("dead", "Dead"),
        ],
        default="pending",
    )
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    # Retry tracking
    attempt_count = models.PositiveIntegerField(
        default=0, help_text="Number of delivery attempts made so far."
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the next retry should be attempted.",
    )
    dedupe_key = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text=(
            "Optional caller supplied key for the logical event. Dispatching the "
            "same key to the same endpoint twice creates only one delivery."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["endpoint", "dedupe_key"],
                condition=models.Q(dedupe_key__isnull=False),
                name="webhooks_unique_dedupe_key_per_endpoint",
            )
        ]

    def __str__(self):
        return f"Delivery {self.id} for {self.endpoint.target_url}"

    objects = models.Manager()


class DeadLetterWebhook(models.Model):
    """
    Stores webhook deliveries that have permanently failed after all retries.
    Operators can inspect these and optionally requeue them via the admin
    or the `replay_dead_webhooks` management command.
    """

    delivery = models.OneToOneField(
        WebhookDelivery,
        on_delete=models.CASCADE,
        related_name="dead_letter",
        help_text="The original delivery that exhausted all retries.",
    )
    reason = models.TextField(
        help_text="The final error or non-2xx status that caused permanent failure."
    )
    replayed = models.BooleanField(
        default=False,
        help_text="Whether this entry has been manually requeued for replay.",
    )
    replayed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent replay attempt.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DLQ entry for delivery {self.delivery_id}"

    objects = models.Manager()


class WebhookDeliveryLog(models.Model):
    """
    Persists immutable logs of individual webhook delivery attempts.
    """

    delivery = models.ForeignKey(
        WebhookDelivery,
        on_delete=models.CASCADE,
        related_name="logs",
        help_text="The delivery this attempt is associated with.",
    )
    status_code = models.IntegerField(
        null=True, blank=True, help_text="HTTP status code returned, if any."
    )
    response_body = models.TextField(
        blank=True, help_text="Response body or error details."
    )
    key_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="The key ID used to verify (or attempted) the delivery signature.",
    )
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log for Delivery {self.delivery_id} - Status {self.status_code}"

    objects = models.Manager()


class InboundWebhookEvent(models.Model):
    """
    Observability & replay protection record for inbound webhooks received from third-party services.
    """

    STATUS_CHOICES = [
        ("received", "Received"),
        ("processed", "Processed"),
        ("duplicate", "Duplicate"),
        ("rejected", "Rejected"),
        ("out_of_order", "Out of Order"),
        ("failed", "Failed"),
    ]

    provider = models.CharField(max_length=64, db_index=True)
    event_id = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=128, db_index=True)
    signature_valid = models.BooleanField(default=False)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default="received", db_index=True
    )
    payload = models.JSONField(default=dict, blank=True)
    event_timestamp = models.DateTimeField(null=True, blank=True)
    sequence = models.BigIntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")
    replayed = models.BooleanField(default=False)
    replayed_at = models.DateTimeField(null=True, blank=True)
    replayed_by = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                condition=models.Q(event_id__gt=""),
                name="webhooks_unique_provider_event_id",
            )
        ]

    def __str__(self):
        return f"[{self.provider}] {self.event_type} ({self.event_id}) - {self.status}"
