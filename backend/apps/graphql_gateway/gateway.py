"""
GraphQL Federation Gateway using Apollo Federation.
"""

import os
import requests
from typing import Dict, Any, List, Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Service Registry
# ============================================================


class ServiceRegistry:
    """
    Registry for GraphQL subgraph services.
    """

    _services: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_service(cls, name: str, url: str, schema: Optional[str] = None):
        """
        Register a subgraph service.

        Args:
            name: Service name (e.g., 'content', 'progress')
            url: GraphQL endpoint URL
            schema: Optional schema string
        """
        cls._services[name] = {
            "url": url,
            "schema": schema,
            "active": True,
        }
        logger.info(f"Registered service: {name} at {url}")

    @classmethod
    def get_service(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get a service by name."""
        return cls._services.get(name)

    @classmethod
    def get_all_services(cls) -> Dict[str, Dict[str, Any]]:
        """Get all registered services."""
        return cls._services

    @classmethod
    def is_service_active(cls, name: str) -> bool:
        """Check if a service is active."""
        service = cls.get_service(name)
        return service is not None and service.get("active", False)

    @classmethod
    def get_service_url(cls, name: str) -> Optional[str]:
        """Get the URL for a service."""
        service = cls.get_service(name)
        return service.get("url") if service else None


# ============================================================
# Service Discovery
# ============================================================


class ServiceDiscovery:
    """
    Dynamic service discovery for subgraphs.
    """

    _discovery_url = os.getenv("DISCOVERY_URL", None)

    @classmethod
    def discover_services(cls):
        """
        Discover services from a discovery endpoint.
        """
        if not cls._discovery_url:
            logger.warning("No discovery URL configured")
            return

        try:
            response = requests.get(cls._discovery_url, timeout=5)
            response.raise_for_status()
            services = response.json()

            for service in services:
                ServiceRegistry.register_service(
                    service["name"], service["url"], service.get("schema")
                )

            logger.info(f"Discovered {len(services)} services")
        except Exception as e:
            logger.error(f"Service discovery failed: {e}")


# ============================================================
# GraphQL Router
# ============================================================


class GraphQLRouter:
    """
    GraphQL federation router that delegates queries to subgraphs.
    """

    def __init__(self):
        self.services = {}
        self._initialize_services()

    def _initialize_services(self):
        """Initialize services from environment or registry."""
        # Register services from environment
        service_map = {
            "content": os.getenv(
                "CONTENT_SERVICE_URL", "http://localhost:8001/graphql"
            ),
            "progress": os.getenv(
                "PROGRESS_SERVICE_URL", "http://localhost:8002/graphql"
            ),
            "users": os.getenv("USERS_SERVICE_URL", "http://localhost:8003/graphql"),
            "chat": os.getenv("CHAT_SERVICE_URL", "http://localhost:8004/graphql"),
            "notifications": os.getenv(
                "NOTIFICATIONS_SERVICE_URL", "http://localhost:8005/graphql"
            ),
        }

        for name, url in service_map.items():
            if url:
                ServiceRegistry.register_service(name, url)

        # Try dynamic discovery
        ServiceDiscovery.discover_services()

    def route_query(
        self, query: str, variables: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Route a GraphQL query to the appropriate subgraph.
        """
        # Parse query to determine service(s)
        services = self._determine_services(query)

        if len(services) == 0:
            return {"errors": [{"message": "No service found for query"}]}

        # Execute on each service
        results = {}
        for service in services:
            try:
                result = self._execute_on_service(service, query, variables)
                results[service] = result
            except Exception as e:
                logger.error(f"Service {service} error: {e}")
                results[service] = {"errors": [{"message": str(e)}]}

        # Merge results (simple implementation)
        # For production, use Apollo Federation or schema stitching
        return self._merge_results(results)

    def _determine_services(self, query: str) -> List[str]:
        """
        Determine which services are needed for the query.

        This is a simple implementation. In production,
        use Apollo Federation's query planner.
        """
        services = []

        # Content service
        if any(
            field in query
            for field in ["content", "contents", "module", "modules", "lesson"]
        ):
            services.append("content")

        # Progress service
        if any(field in query for field in ["progress", "userProgress", "badge"]):
            services.append("progress")

        # User service
        if any(field in query for field in ["user", "users", "me"]):
            services.append("users")

        # Chat service
        if any(
            field in query
            for field in ["conversation", "conversations", "message", "messages"]
        ):
            services.append("chat")

        # Notifications service
        if any(
            field in query for field in ["notification", "notifications", "unreadCount"]
        ):
            services.append("notifications")

        return services or ["content"]  # Default to content

    def _execute_on_service(
        self, service: str, query: str, variables: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute a query on a specific service.
        """
        url = ServiceRegistry.get_service_url(service)
        if not url:
            return {"errors": [{"message": f"Service {service} not available"}]}

        try:
            response = requests.post(
                url,
                json={"query": query, "variables": variables or {}},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"errors": [{"message": f"Service {service} timeout"}]}
        except requests.exceptions.RequestException as e:
            return {"errors": [{"message": f"Service {service} error: {str(e)}"}]}

    def _merge_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge results from multiple services.

        In production, use Apollo Federation's result composition.
        """
        merged = {"data": {}, "errors": []}

        for service, result in results.items():
            if "data" in result:
                for key, value in result["data"].items():
                    if key not in merged["data"]:
                        merged["data"][key] = value
                    elif isinstance(value, list):
                        merged["data"][key].extend(value)
            if "errors" in result:
                merged["errors"].extend(result["errors"])

        return merged

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of all services.
        """
        health = {}
        for name, service in ServiceRegistry.get_all_services().items():
            try:
                response = requests.get(f"{service['url']}/health", timeout=2)
                health[name] = {"status": "healthy", "code": response.status_code}
            except Exception:
                health[name] = {"status": "unhealthy", "code": None}

        return health


# ============================================================
# Federation Query Planner (Simplified)
# ============================================================


class FederationQueryPlanner:
    """
    Simplified query planner for federation.

    In production, use Apollo Federation's full implementation.
    """

    def __init__(self, router: GraphQLRouter):
        self.router = router

    def plan(
        self, query: str, variables: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Plan the query execution across services.
        """
        return [
            {"service": service, "query": query, "variables": variables}
            for service in self.router._determine_services(query)
        ]

    def execute(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute the planned query.
        """
        return self.router.route_query(query, variables)


# ============================================================
# Singleton Instance
# ============================================================

_graphql_router = None


def get_graphql_router() -> GraphQLRouter:
    """Get the singleton GraphQL router instance."""
    global _graphql_router
    if _graphql_router is None:
        _graphql_router = GraphQLRouter()
    return _graphql_router


def execute_graphql(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Execute a GraphQL query through the federation gateway.
    """
    router = get_graphql_router()
    return router.route_query(query, variables)
