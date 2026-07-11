"""
GraphQL gateway views for federation.
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.graphql_gateway.gateway import get_graphql_router, execute_graphql

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def graphql_gateway(request):
    """
    GraphQL federation gateway endpoint.

    Handles both GET (query string) and POST (JSON body) requests.
    """
    if request.method == "GET":
        query = request.GET.get("query", "")
        variables = request.GET.get("variables", "{}")
        try:
            variables = json.loads(variables)
        except json.JSONDecodeError:
            variables = {}
    else:
        try:
            data = json.loads(request.body)
            query = data.get("query", "")
            variables = data.get("variables", {})
        except json.JSONDecodeError:
            return JsonResponse(
                {"errors": [{"message": "Invalid JSON body"}]}, status=400
            )

    if not query:
        return JsonResponse({"errors": [{"message": "Query is required"}]}, status=400)

    try:
        # Execute through federation gateway
        result = execute_graphql(query, variables)
        return JsonResponse(result, status=200)
    except Exception as e:
        logger.error(f"GraphQL gateway error: {e}", exc_info=True)
        return JsonResponse({"errors": [{"message": str(e)}]}, status=500)


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
