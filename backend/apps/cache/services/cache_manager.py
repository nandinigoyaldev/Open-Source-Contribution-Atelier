"""
Cache manager with write-through and invalidation strategies.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Type, Union
from functools import wraps
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from apps.cache.models import CacheDependency, CacheConfig

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages cache operations with write-through and invalidation.
    """

    def __init__(self):
        self.default_ttl = 300
        self.version = 1

    def get_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a consistent cache key.

        Args:
            prefix: Key prefix
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            str: Cache key
        """
        # Sort kwargs for consistency
        sorted_kwargs = sorted(kwargs.items())

        # Create a unique string
        key_parts = [prefix, str(self.version)]
        if args:
            key_parts.extend(str(arg) for arg in args)
        if sorted_kwargs:
            key_parts.extend(f"{k}:{v}" for k, v in sorted_kwargs)

        # Hash for consistent length
        key_string = ":".join(key_parts)
        hashed = hashlib.md5(key_string.encode()).hexdigest()[:16]

        return f"cache:{prefix}:{hashed}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Any: Cached value or default
        """
        value = cache.get(key)
        if value is None:
            logger.debug(f"Cache miss: {key}")
            return default

        logger.debug(f"Cache hit: {key}")
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in cache with write-through.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            bool: Success status
        """
        ttl = ttl or self.default_ttl
        result = cache.set(key, value, ttl)

        if result:
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True

        logger.warning(f"Cache set failed: {key}")
        return False

    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            bool: Success status
        """
        result = cache.delete(key)
        if result:
            logger.debug(f"Cache delete: {key}")
            return True
        return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all cache keys matching a pattern.

        Args:
            pattern: Key pattern

        Returns:
            int: Number of keys deleted
        """
        # Note: This is a simplified implementation using standard django cache backend features
        # In production, use Redis SCAN for better performance if using a Redis backend
        count = 0
        if hasattr(cache, "keys"):
            keys = cache.keys(f"*{pattern}*")  # type: ignore
            for key in keys:
                if cache.delete(key):
                    count += 1
        else:
            logger.warning(
                "Cache backend does not support keys() pattern extraction natively."
            )

        logger.info(f"Cleared {count} keys matching pattern: {pattern}")
        return count

    def track_dependency(
        self, source: models.Model, target: models.Model, cache_key: str
    ):
        """
        Track a dependency between models for cache invalidation.

        Args:
            source: Source model instance
            target: Target model instance
            cache_key: Cache key that depends on these objects
        """
        source_ct = ContentType.objects.get_for_model(source)
        target_ct = ContentType.objects.get_for_model(target)

        dependency, created = CacheDependency.objects.get_or_create(
            source_content_type=source_ct,
            source_object_id=source.pk,
            target_content_type=target_ct,
            target_object_id=target.pk,
            cache_key=cache_key,
        )

        if created:
            logger.debug(
                f"Created cache dependency: {source} -> {target} ({cache_key})"
            )

    def invalidate_dependencies(self, target: models.Model):
        """
        Invalidate all cache keys that depend on a target object.

        Args:
            target: Target model instance that changed
        """
        target_ct = ContentType.objects.get_for_model(target)

        # Find all dependencies where this object is the target
        dependencies = CacheDependency.objects.filter(
            target_content_type=target_ct, target_object_id=target.pk
        )

        keys_invalidated = set()
        for dep in dependencies:
            keys_invalidated.add(dep.cache_key)
            dep.delete()

        # Delete from cache
        for key in keys_invalidated:
            self.delete(key)

        if keys_invalidated:
            logger.info(f"Invalidated {len(keys_invalidated)} cache keys for {target}")

        # Also invalidate parent dependencies (cascade)
        self.invalidate_dependencies_cascade(target)

    def invalidate_dependencies_cascade(self, target: models.Model):
        """
        Cascade invalidation to related objects.

        Args:
            target: Target model instance
        """
        # Find objects that have this as a foreign key
        for field in target._meta.get_fields():
            if field.is_relation and field.many_to_one:
                related_manager = getattr(target, field.name, None)
                if related_manager:
                    try:
                        parent = getattr(target, field.name)
                        if parent:
                            self.invalidate_dependencies(parent)
                    except Exception:
                        logger.exception(
                            "Failed to invalidate parent cache dependency."
                        )

    def warm_cache(self, model_name: str):
        """
        Warm cache for a specific model.

        Args:
            model_name: Name of the model to warm
        """
        try:
            config = CacheConfig.objects.get(model_name=model_name, is_active=True)

            if not config.warm_on_startup or not config.warm_queries:
                return

            # Execute warm queries
            for query_config in config.warm_queries:
                # This is a simplified implementation
                # In production, execute actual queries and cache results
                logger.info(f"Warming cache for {model_name}: {query_config}")

        except CacheConfig.DoesNotExist:
            logger.debug(f"No cache config found for {model_name}")

    def invalidate_entire_model(self, model: Type[models.Model]):
        """
        Invalidate all cache for a specific model.

        Args:
            model: Model class to invalidate
        """
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"

        # Clear all dependencies for this model
        content_type = ContentType.objects.get_for_model(model)
        CacheDependency.objects.filter(target_content_type=content_type).delete()

        # Clear all cache keys for this model
        pattern = f"*{model_name}*"
        self.clear_pattern(pattern)

        logger.info(f"Invalidated all cache for {model_name}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict: Cache statistics
        """
        return {
            "total_dependencies": CacheDependency.objects.count(),
            "cache_configs": CacheConfig.objects.filter(is_active=True).count(),
            "warm_enabled": CacheConfig.objects.filter(warm_on_startup=True).count(),
        }


# ============================================================
# Cache Decorators
# ============================================================


class cached:
    """
    Decorator for caching function results.

    Usage:
        @cached(prefix='user_stats', ttl=300)
        def get_user_stats(user_id):
            return compute_stats(user_id)
    """

    def __init__(
        self,
        prefix: str = "",
        ttl: Optional[int] = None,
        dependencies: Optional[List[str]] = None,
    ):
        self.prefix = prefix
        self.ttl = ttl
        self.dependencies = dependencies or []
        self.manager = CacheManager()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = self.manager.get_cache_key(self.prefix, *args, **kwargs)

            # Try to get from cache
            result = self.manager.get(key)
            if result is not None:
                return result

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            self.manager.set(key, result, self.ttl)

            return result

        return wrapper


class invalidates:
    """
    Decorator for invalidating cache after function execution.

    Usage:
        @invalidates('user_stats')
        def update_user(user_id):
            return update_user_in_db(user_id)
    """

    def __init__(self, *patterns):
        self.patterns = patterns
        self.manager = CacheManager()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Invalidate cache patterns
            for pattern in self.patterns:
                self.manager.clear_pattern(pattern)

            return result

        return wrapper


# ============================================================
# Signal Handlers for Automatic Invalidation
# ============================================================

# Flag to disable signals during migrations
_cache_signals_enabled = True


def disable_cache_signals():
    """Disable cache invalidation signals (used during migrations)"""
    global _cache_signals_enabled
    _cache_signals_enabled = False


def enable_cache_signals():
    """Re-enable cache invalidation signals"""
    global _cache_signals_enabled
    _cache_signals_enabled = True


def _is_migration_in_progress():
    """Check if Django is running migrations"""
    import sys

    # Check if we're in a manage.py command (migration)
    if "manage.py" in sys.argv and "migrate" in sys.argv:
        return True
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            # Check if contenttypes table has the name column properly
            cursor.execute("PRAGMA table_info(django_content_type)")
            columns = {row[1] for row in cursor.fetchall()}
            return "name" not in columns
    except Exception:
        return True


@receiver(post_save)
def invalidate_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalidate cache when a model is saved.
    """
    if not _cache_signals_enabled:
        return

    # Skip during migrations or when system apps are involved
    if _is_migration_in_progress() or sender._meta.app_label in [
        "migrations",
        "contenttypes",
        "sessions",
        "admin",
        "sites",
        "auth",
    ]:
        return

    try:
        manager = CacheManager()
        manager.invalidate_dependencies(instance)
    except Exception as e:
        logger.warning(
            "Cache invalidation failed after saving %s: %s",
            instance,
            e,
        )


@receiver(post_delete)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate cache when a model is deleted.
    """
    if not _cache_signals_enabled:
        return

    # Skip during migrations or for Django system apps
    if _is_migration_in_progress():
        return

    if sender._meta.app_label in [
        "migrations",
        "contenttypes",
        "sessions",
        "admin",
        "sites",
        "auth",
    ]:
        return

    try:
        manager = CacheManager()
        manager.invalidate_dependencies(instance)
    except Exception as e:
        logger.warning(
            "Cache invalidation failed after deleting %s: %s",
            instance,
            e,
        )


@receiver(m2m_changed)
def invalidate_cache_on_m2m_change(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    """
    Invalidate cache when a many-to-many relationship changes.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        manager = CacheManager()
        try:
            manager.invalidate_dependencies(instance)
        except Exception as e:
            logger.warning(
                "Cache invalidation failed for M2M change on %s: %s",
                instance,
                e,
            )

        # Also invalidate for related objects
        if pk_set:
            for pk in pk_set:
                try:
                    related = model.objects.get(pk=pk)
                    try:
                        manager.invalidate_dependencies(related)
                    except Exception as e:
                        logger.warning(
                            "Cache invalidation failed for related object with pk=%s: %s",
                            pk,
                            e,
                        )
                except model.DoesNotExist:
                    pass
