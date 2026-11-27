from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import AITokenUsageLedger
from .token_budget import clear_counters


@receiver(post_delete, sender=AITokenUsageLedger)
def clear_counters_of_deleted_row(sender, instance, **kwargs):
    # Deleting a row (in the admin, or with its user) resets that day. Without this
    # the cached total would keep counting, and the flush only walks existing rows.
    clear_counters(instance.user_id, instance.date)
