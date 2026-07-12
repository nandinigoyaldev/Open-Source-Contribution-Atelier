"""
App configuration for GraphQL gateway.
"""

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class GraphQLGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.graphql_gateway"
    label = "graphql_gateway"
    verbose_name = "GraphQL Federation Gateway"

    def ready(self):
        """
        Initialize the GraphQL gateway.
        """
        try:
            from apps.graphql_gateway.gateway import get_graphql_router

            router = get_graphql_router()
            logger.info("GraphQL gateway initialized successfully")

            # Log registered services
            for name, service in router.services.items():
                logger.info(f"Service registered: {name} -> {service.get('url')}")

        except Exception as e:
            logger.warning(f"Failed to initialize GraphQL gateway: {e}")
