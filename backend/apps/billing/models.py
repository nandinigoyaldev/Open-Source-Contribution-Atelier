from django.conf import settings
from django.db import models


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    stripe_price_id = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=list)

    def __str__(self):
        return self.name


class CustomerSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
        null=True,
        blank=True,
    )
    # If organizations exist, we can optionally link it here as well
    # organization = models.OneToOneField('organizations.Organization', on_delete=models.CASCADE, null=True, blank=True)

    stripe_customer_id = models.CharField(max_length=100, unique=True)
    stripe_subscription_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    active = models.BooleanField(default=False)
    status = models.CharField(max_length=50, default="inactive")
    current_period_end = models.DateTimeField(null=True, blank=True)
    payment_failed_at = models.DateTimeField(null=True, blank=True)
    # Stripe `created` time of the newest event applied to the subscription this
    # row follows. Older events go in the StripeEvent ledger but change nothing.
    last_event_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Subscription for {self.user}"


class OrganizationSponsor(models.Model):
    name = models.CharField(max_length=255)
    website = models.URLField(blank=True, null=True)
    stripe_account_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name


class Bounty(models.Model):
    sponsor = models.ForeignKey(
        OrganizationSponsor, on_delete=models.CASCADE, related_name="bounties"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.amount} {self.currency}"


class BountyClaim(models.Model):
    bounty = models.ForeignKey(Bounty, on_delete=models.CASCADE, related_name="claims")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bounty_claims"
    )
    is_approved = models.BooleanField(default=False)
    payout_id = models.CharField(
        max_length=100, blank=True, null=True, help_text="Stripe transfer/payout ID"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Claim by {self.user} for {self.bounty}"


class Invoice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices"
    )
    stripe_invoice_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=50
    )  # e.g., 'paid', 'open', 'uncollectible', 'void'
    pdf_file = models.FileField(upload_to="invoices/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice {self.stripe_invoice_id or self.id} - {self.amount}"


class Payment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    stripe_charge_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=50)  # e.g., 'succeeded', 'failed', 'pending'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.stripe_charge_id} - {self.amount} {self.currency}"


class StripeEvent(models.Model):
    """
    One row per Stripe event handled by the webhook.

    The row is written in the same transaction as whatever the event changes, so
    a crash leaves neither and Stripe's retry starts clean. The unique event_id
    is what stops a second delivery from applying anything.
    """

    OUTCOME_APPLIED = "applied"
    OUTCOME_STALE = "stale"
    OUTCOME_UNMATCHED = "unmatched"
    OUTCOME_IGNORED = "ignored"
    OUTCOME_CHOICES = [
        (OUTCOME_APPLIED, "Applied"),
        (OUTCOME_STALE, "Stale: older than the saved state"),
        (OUTCOME_UNMATCHED, "Unmatched: no local subscription for it"),
        (OUTCOME_IGNORED, "Ignored: event type is not handled"),
    ]

    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=255, blank=True)
    customer_id = models.CharField(max_length=255, blank=True)
    event_created_at = models.DateTimeField()
    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default=OUTCOME_IGNORED
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_created_at"]
        indexes = [models.Index(fields=["outcome", "event_created_at"])]

    def __str__(self):
        return f"{self.event_id} ({self.event_type}): {self.outcome}"
