from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache

from .models import Lesson

def clear_curriculum_caches():
    cache.delete("active_lessons_list")

@receiver([post_save, post_delete], sender=Lesson)
def invalidate_lesson_cache(sender, instance, **kwargs):
    # Ensure cache is cleared only after DB transaction is successfully committed
    transaction.on_commit(lambda: clear_curriculum_caches())
