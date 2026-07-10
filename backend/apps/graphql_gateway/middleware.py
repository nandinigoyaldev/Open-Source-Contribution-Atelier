"""
Middleware for GraphQL gateway.
"""

import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class GraphQLGatewayMiddleware(MiddlewareMixin):
    """
    Middleware for GraphQL gateway monitoring and logging.
    """

    def process_request(self, request):
        """Process request and log GraphQL queries."""
        if request.path.startswith("/api/graphql/graphql/"):
            if request.method == "POST":
                try:
                    import json

                    data = json.loads(request.body)
                    query = data.get("query", "")[:200]
                    logger.info(f"GraphQL query: {query}...")
                except:
                    pass

        return None

    def process_response(self, request, response):
        """Process response and add headers."""
        if request.path.startswith("/api/graphql/graphql/"):
            response["X-GraphQL-Gateway"] = "federation-v1"
        return response
