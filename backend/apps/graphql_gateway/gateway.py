"""
GraphQL Federation Gateway using Apollo Federation.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import requests
from graphql import parse
from graphql.language.ast import FieldNode, OperationDefinitionNode

logger = logging.getLogger(__name__)


def get_ast_depth(node, current_depth=1):
    if not hasattr(node, "selection_set") or not node.selection_set:
        return current_depth
    max_depth = current_depth
    for selection in node.selection_set.selections:
        depth = get_ast_depth(selection, current_depth + 1)
        max_depth = max(max_depth, depth)
    return max_depth


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
        self._circuit_breakers = {}
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
        self,
        query: str,
        variables: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Route a GraphQL query to the appropriate subgraph.
        """
        try:
            ast = parse(query)
        except Exception as e:
            return {"errors": [{"message": f"GraphQL Parsing Error: {str(e)}"}]}

        for definition in ast.definitions:
            if get_ast_depth(definition) > 10:
                return {"errors": [{"message": "Query depth exceeds limit of 10"}]}

        services = self._determine_services(ast)

        if len(services) == 0:
            return {"errors": [{"message": "No service found for query"}]}

        # Execute on each service
        results = {}
        for service in services:
            try:
                result = self._execute_on_service(service, query, variables, headers)
                results[service] = result
            except Exception as e:
                logger.error(f"Service {service} error: {e}")
                results[service] = {"errors": [{"message": str(e)}]}

        return self._merge_results(results)

    def _determine_services(self, ast) -> List[str]:
        """
        Determine which services are needed for the query using AST.
        """
        services = set()
        for definition in ast.definitions:
            if (
                isinstance(definition, OperationDefinitionNode)
                and definition.selection_set
            ):
                for selection in definition.selection_set.selections:
                    if isinstance(selection, FieldNode):
                        field_name = selection.name.value

                        if field_name in [
                            "content",
                            "contents",
                            "module",
                            "modules",
                            "lesson",
                        ]:
                            services.add("content")
                        elif field_name in ["progress", "userProgress", "badge"]:
                            services.add("progress")
                        elif field_name in ["user", "users", "me"]:
                            services.add("users")
                        elif field_name in [
                            "conversation",
                            "conversations",
                            "message",
                            "messages",
                        ]:
                            services.add("chat")
                        elif field_name in [
                            "notification",
                            "notifications",
                            "unreadCount",
                        ]:
                            services.add("notifications")

        if not services:
            services.add("content")

        return list(services)

    def _execute_on_service(
        self,
        service: str,
        query: str,
        variables: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Execute a query on a specific service with circuit breaking.
        """
        cb_state = self._circuit_breakers.setdefault(
            service, {"failures": 0, "open": False}
        )
        if cb_state["open"]:
            return {
                "errors": [
                    {
                        "message": f"Service {service} is currently unavailable (circuit open)"
                    }
                ]
            }

        url = ServiceRegistry.get_service_url(service)
        if not url:
            return {"errors": [{"message": f"Service {service} not available"}]}

        try:
            req_headers = {"Content-Type": "application/json"}
            if headers:
                req_headers.update(headers)

            response = requests.post(
                url,
                json={"query": query, "variables": variables or {}},
                headers=req_headers,
                timeout=10,
            )
            response.raise_for_status()

            cb_state["failures"] = 0
            cb_state["open"] = False
            return response.json()
        except requests.exceptions.Timeout:
            cb_state["failures"] += 1
            if cb_state["failures"] >= 5:
                cb_state["open"] = True
            return {"errors": [{"message": f"Service {service} timeout"}]}
        except requests.exceptions.RequestException as e:
            cb_state["failures"] += 1
            if cb_state["failures"] >= 5:
                cb_state["open"] = True
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
        self,
        query: str,
        variables: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Plan the query execution across services.
        """
        return [
            {"service": service, "query": query, "variables": variables}
            for service in self.router._determine_services(parse(query))
        ]

    def execute(
        self,
        query: str,
        variables: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Execute the planned query.
        """
        return self.router.route_query(query, variables, headers)


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


def execute_graphql(
    query: str, variables: Optional[Dict] = None, headers: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Execute a GraphQL query through the federation gateway.
    """
    router = get_graphql_router()
    return router.route_query(query, variables, headers)
