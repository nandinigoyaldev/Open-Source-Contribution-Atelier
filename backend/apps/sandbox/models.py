from django.conf import settings
from django.db import models


class SandboxExecutionLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sandbox_execution_logs",
        help_text="The user who attempted the command.",
    )
    command = models.TextField(help_text="The command the user attempted to execute.")
    accepted = models.BooleanField(help_text="Whether the command was accepted.")
    feedback = models.TextField(blank=True, help_text="Feedback returned to the user.")
    score_delta = models.IntegerField(
        help_text="Score change resulting from this attempt."
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the attempt was made."
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.get_username() if self.user else "Anonymous"
        cmd_preview = (
            (self.command[:47] + "...") if len(self.command) > 50 else self.command
        )
        return (
            f"[{'Accepted' if self.accepted else 'Rejected'}] {username}: {cmd_preview}"
        )
