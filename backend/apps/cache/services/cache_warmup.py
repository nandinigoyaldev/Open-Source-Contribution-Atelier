"""
Cache warming service for dashboard endpoints.
"""

import logging
from typing import List, Dict, Any
from django.core.management import call_command
from django.apps import apps
from apps.cache.models import CacheConfig
from apps.cache.services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class CacheWarmupService:
    """
    Service for warming cache on startup and on demand.
    """

    def __init__(self):
        self.manager = CacheManager()

    def warm_all(self):
        """
        Warm all caches based on configuration.
        """
        configs = CacheConfig.objects.filter(is_active=True, warm_on_startup=True)

        for config in configs:
            try:
                self.warm_model(config.model_name)
            except Exception as e:
                logger.error(f"Failed to warm cache for {config.model_name}: {e}")

    def warm_model(self, model_name: str):
        """
        Warm cache for a specific model.

        Args:
            model_name: Name of the model
        """
        try:
            config = CacheConfig.objects.get(model_name=model_name, is_active=True)

            if not config.warm_queries:
                return

            # Parse model
            app_label, model_name = config.model_name.split(".")
            model = apps.get_model(app_label, model_name)

            # Execute warm queries
            for query_config in config.warm_queries:
                self._execute_warm_query(model, query_config)

            logger.info(f"Warmed cache for {config.model_name}")

        except CacheConfig.DoesNotExist:
            logger.debug(f"No cache config found for {model_name}")
        except Exception as e:
            logger.error(f"Error warming cache for {model_name}: {e}")

    def _execute_warm_query(self, model, query_config: Dict[str, Any]):
        """
        Execute a warm query and cache the results.

        Args:
            model: Model class
            query_config: Query configuration
        """
        try:
            # Build query
            queryset = model.objects.all()

            # Apply filters
            filters = query_config.get("filters", {})
            if filters:
                queryset = queryset.filter(**filters)

            # Apply ordering
            order_by = query_config.get("order_by")
            if order_by:
                queryset = queryset.order_by(*order_by)

            # Apply limits
            limit = query_config.get("limit")
            if limit:
                queryset = queryset[:limit]

            # Cache the results
            key = self.manager.get_cache_key(
                f"warm:{model._meta.app_label}.{model._meta.model_name}", **query_config
            )

            # Convert to list to evaluate queryset
            results = list(queryset)
            self.manager.set(key, results)

            logger.debug(f"Cached {len(results)} {model._meta.model_name} objects")

        except Exception as e:
            logger.error(f"Error executing warm query: {e}")

    def warm_dashboard(self, user_id: int):
        """
        Warm cache for dashboard endpoints.

        Args:
            user_id: User ID to warm dashboard for
        """
        # Warm progress data
        from apps.progress.models import UserProgress

        progress_cache = self.manager.get_cache_key("user_progress", user_id=user_id)
        progress_data = UserProgress.objects.filter(user_id=user_id)
        self.manager.set(progress_cache, list(progress_data))

        # Warm badges
        from apps.progress.models import UserBadge

        badge_cache = self.manager.get_cache_key("user_badges", user_id=user_id)
        badge_data = UserBadge.objects.filter(user_id=user_id).select_related("badge")
        self.manager.set(badge_cache, list(badge_data))

        # Warm leaderboard
        from apps.dashboard.models import Leaderboard

        leaderboard_cache = self.manager.get_cache_key("leaderboard")
        leaderboard_data = Leaderboard.objects.all().order_by("-points")[:100]
        self.manager.set(leaderboard_cache, list(leaderboard_data))

        logger.info(f"Warmed dashboard cache for user {user_id}")


# ============================================================
# Management Command
# ============================================================

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Management command for cache warmup.
    """

    help = "Warm the cache for configured models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model", type=str, help="Specific model to warm (app_label.model_name)"
        )
        parser.add_argument(
            "--all", action="store_true", help="Warm all configured models"
        )

    def handle(self, *args, **options):
        service = CacheWarmupService()

        if options.get("all"):
            self.stdout.write("Warming all caches...")
            service.warm_all()
            self.stdout.write("✅ Cache warmup complete")
        elif options.get("model"):
            self.stdout.write(f'Warming cache for {options["model"]}...')
            service.warm_model(options["model"])
            self.stdout.write("✅ Cache warmup complete")
        else:
            self.stdout.write("Please specify --all or --model")
