"""
GraphQL gateway views for federation.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.graphql_gateway.gateway import execute_graphql, get_graphql_router

logger = logging.getLogger(__name__)


from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.throttling import SlidingWindowAnonThrottle, SlidingWindowUserThrottle
from rest_framework.views import APIView


class GraphQLGatewayView(APIView):
    """
    GraphQL federation gateway endpoint with Auth and Rate Limiting.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [SlidingWindowUserThrottle, SlidingWindowAnonThrottle]

    def get(self, request):
        return self._handle_request(request)

    def post(self, request):
        return self._handle_request(request)

    def _handle_request(self, request):
        if request.method == "GET":
            query = request.query_params.get("query", "")
            variables = request.query_params.get("variables", "{}")
            try:
                variables = json.loads(variables)
            except json.JSONDecodeError:
                variables = {}
        else:
            query = request.data.get("query", "")
            variables = request.data.get("variables", {})

        if not query:
            return Response({"errors": [{"message": "Query is required"}]}, status=400)

        # Pass Authorization header down to subgraphs
        auth_header = request.headers.get("Authorization")
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header

        try:
            # Execute through federation gateway
            result = execute_graphql(query, variables, headers=headers)
            return Response(result, status=200)
        except Exception as e:
            logger.error(f"GraphQL gateway error: {e}", exc_info=True)
            return Response({"errors": [{"message": str(e)}]}, status=500)


@csrf_exempt
def graphql_gateway_health(request):
    """
    Health check for the graphql gateway.
    """
    router = get_graphql_router()
    health = router.get_health()

    # Overall status
    status = all(s.get("status") == "healthy" for s in health.values())

    return JsonResponse(
        {
            "status": "healthy" if status else "degraded",
            "services": health,
        }
    )


@csrf_exempt
def graphql_introspection(request):
    """
    Get the combined schema from all services.
    """
    # In production, this would combine schemas from all subgraphs
    # For now, return a simple schema
    return JsonResponse(
        {
            "data": {
                "__schema": {
                    "types": [
                        {"name": "Query"},
                        {"name": "Mutation"},
                        {"name": "Content"},
                        {"name": "Module"},
                        {"name": "Lesson"},
                        {"name": "Progress"},
                        {"name": "User"},
                        {"name": "Conversation"},
                        {"name": "Message"},
                        {"name": "Notification"},
                    ]
                }
            }
        }
    )
