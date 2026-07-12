"""
Write-through cache implementation for models.
"""

import logging
from typing import Any, Dict, List, Optional, Type, Union
from django.core.cache import cache
from django.db import models, transaction
from apps.cache.services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class WriteThroughCache:
    """
    Write-through cache for models with dependency tracking.
    """

    def __init__(self, model: Type[models.Model]):
        self.model = model
        self.manager = CacheManager()
        self.model_name = f"{model._meta.app_label}.{model._meta.model_name}"

    def get(self, pk: Any, field: Optional[str] = None) -> Optional[Any]:
        """
        Get a model instance from cache or database.

        Args:
            pk: Primary key
            field: Specific field to get

        Returns:
            Optional[Any]: Model instance or field value
        """
        # Generate cache key
        if field:
            key = self.manager.get_cache_key(
                f"{self.model_name}:field", pk=pk, field=field
            )
        else:
            key = self.manager.get_cache_key(f"{self.model_name}:instance", pk=pk)

        # Try cache
        cached_data = self.manager.get(key)
        if cached_data is not None:
            return cached_data

        # Query database
        try:
            instance = self.model.objects.get(pk=pk)

            if field:
                result = getattr(instance, field)
            else:
                result = instance

            # Cache the result
            self.manager.set(key, result)

            # Track dependencies
            self._track_dependencies(instance, key)

            return result

        except self.model.DoesNotExist:
            return None

    def set(self, instance: models.Model) -> bool:
        """
        Write a model instance through cache (write-through).

        Args:
            instance: Model instance to write

        Returns:
            bool: Success status
        """
        with transaction.atomic():
            # Save to database
            instance.save()

            # Update cache
            key = self.manager.get_cache_key(
                f"{self.model_name}:instance", pk=instance.pk
            )
            self.manager.set(key, instance)

            # Track dependencies
            self._track_dependencies(instance, key)

            # Invalidate related caches
            self.manager.invalidate_dependencies(instance)

            logger.info(f"Write-through completed for {self.model_name}: {instance.pk}")
            return True

    def delete(self, pk: Any) -> bool:
        """
        Delete a model instance through cache.

        Args:
            pk: Primary key

        Returns:
            bool: Success status
        """
        with transaction.atomic():
            try:
                instance = self.model.objects.get(pk=pk)
                instance.delete()

                # Delete from cache
                key = self.manager.get_cache_key(f"{self.model_name}:instance", pk=pk)
                self.manager.delete(key)

                # Invalidate dependencies
                self.manager.invalidate_dependencies(instance)

                logger.info(
                    f"Write-through delete completed for {self.model_name}: {pk}"
                )
                return True

            except self.model.DoesNotExist:
                logger.warning(f"Model not found for deletion: {self.model_name}: {pk}")
                return False

    def _track_dependencies(self, instance: models.Model, cache_key: str):
        """
        Track dependencies for a model instance.

        Args:
            instance: Model instance
            cache_key: Cache key that depends on this instance
        """
        # Track foreign key relationships
        for field in instance._meta.get_fields():
            if field.is_relation and field.many_to_one:
                try:
                    related = getattr(instance, field.name)
                    if related:
                        self.manager.track_dependency(instance, related, cache_key)
                except:
                    pass


class WriteThroughCacheManager:
    """
    Manager for write-through cache operations.
    """

    _caches = {}

    @classmethod
    def get_cache(cls, model: Type[models.Model]) -> WriteThroughCache:
        """
        Get or create a write-through cache for a model.

        Args:
            model: Model class

        Returns:
            WriteThroughCache: Write-through cache instance
        """
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"

        if model_name not in cls._caches:
            cls._caches[model_name] = WriteThroughCache(model)

        return cls._caches[model_name]

    @classmethod
    def get_or_create(
        cls, model: Type[models.Model], defaults: Dict = None, **kwargs
    ) -> tuple:
        """
        Get or create a model instance with write-through cache.

        Args:
            model: Model class
            defaults: Default values for creation
            **kwargs: Query parameters

        Returns:
            tuple: (instance, created)
        """
        cache = cls.get_cache(model)

        # Try to get from cache or database
        try:
            # Try to get existing
            instance = model.objects.get(**kwargs)
            return instance, False
        except model.DoesNotExist:
            # Create new
            instance = model(**kwargs)
            if defaults:
                for key, value in defaults.items():
                    setattr(instance, key, value)
            cache.set(instance)
            return instance, True


class StaleWhileRevalidateCache(WriteThroughCache):
    """
    Stale-While-Revalidate cache strategy.
    """

    def __init__(self, model: Type[models.Model], stale_ttl: int = 60):
        super().__init__(model)
        self.stale_ttl = stale_ttl

    def get(self, pk: Any, field: Optional[str] = None) -> Optional[Any]:
        """
        Get with stale-while-revalidate strategy.

        Args:
            pk: Primary key
            field: Specific field to get

        Returns:
            Optional[Any]: Model instance or field value
        """
        key = self.manager.get_cache_key(
            f"{self.model_name}:swr", pk=pk, field=field or "instance"
        )

        # Try cache
        cached_data = self.manager.get(key)

        if cached_data is not None:
            # Check if it's stale (for async revalidation)
            # In production, check timestamp and trigger background refresh
            return cached_data

        # Query database
        try:
            instance = self.model.objects.get(pk=pk)

            if field:
                result = getattr(instance, field)
            else:
                result = instance

            # Cache with longer TTL (stale)
            self.manager.set(key, result, self.stale_ttl)

            return result

        except self.model.DoesNotExist:
            return None
