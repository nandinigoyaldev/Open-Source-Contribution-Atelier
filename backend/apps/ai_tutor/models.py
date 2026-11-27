# The Django field stubs in use type ``default=`` as a class and do not know the
# ``<fk>_id`` attributes or field arithmetic, so those are reported. They are valid Django.
# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOperatorIssue=false
from django.conf import settings
from django.db import models


class AITokenUsageLedger(models.Model):
    """
    LLM tokens one user spent on the AI tutor during one UTC day.

    Requests bump counters in the cache (see token_budget.py). The
    flush_ai_token_usage task copies those totals in here, so a row can lag
    the live usage by up to one flush interval.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_token_usage",
    )
    date = models.DateField(help_text="UTC day the usage belongs to")
    input_tokens = models.PositiveBigIntegerField(default=0)
    output_tokens = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="ai_token_ledger_user_date_unique"
            )
        ]
        indexes = [models.Index(fields=["date"], name="ai_token_ledger_date_idx")]

    def __str__(self) -> str:
        return f"{self.user_id} {self.date}: {self.total_tokens} tokens"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class AITokenBudgetOverride(models.Model):
    """Admin set daily token limit for one user. Wins over the tier and org pool."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_token_budget_override",
    )
    daily_token_limit = models.PositiveIntegerField(
        help_text="Tokens per UTC day for this user. 0 blocks the AI tutor for them."
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Leave empty to keep the override until it is deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user_id}: {self.daily_token_limit} tokens/day"

    def is_active(self, now) -> bool:
        return self.expires_at is None or self.expires_at > now


class AITokenOrganizationPool(models.Model):
    """
    Daily token budget shared by every member of an organization.

    Members are the users whose profile points at the organization. While the
    pool is active their own tier limit is not used, the whole org draws from
    this one budget instead.
    """

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="ai_token_pool",
    )
    daily_token_limit = models.PositiveIntegerField(
        help_text="Tokens per UTC day shared by all members"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.organization_id}: {self.daily_token_limit} tokens/day"
