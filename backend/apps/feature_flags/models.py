from django.core.cache import cache
from django.db import models

CACHE_KEY_ALL_FLAGS = "feature_flags:all"
CACHE_TTL = 300  # 5 minutes


class FeatureFlagManager(models.Manager):
    def is_enabled(self, name: str, default: bool = False) -> bool:
        flags = self.all_flags()
        return flags.get(name, {}).get("enabled", default)

    def all_flags(self) -> dict:
        flags = cache.get(CACHE_KEY_ALL_FLAGS)
        if flags is not None:
            return flags
        qs = self.values("name", "enabled")
        flags = {f["name"]: f for f in qs}
        cache.set(CACHE_KEY_ALL_FLAGS, flags, CACHE_TTL)
        return flags

    def invalidate_cache(self) -> None:
        cache.delete(CACHE_KEY_ALL_FLAGS)


class FeatureFlag(models.Model):
    name = models.SlugField(
        max_length=100, unique=True, help_text="Unique identifier for the flag."
    )
    enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")

    objects = FeatureFlagManager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name}: {'ON' if self.enabled else 'OFF'}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        FeatureFlag.objects.invalidate_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        FeatureFlag.objects.invalidate_cache()
