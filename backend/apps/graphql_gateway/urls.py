"""
URL configuration for GraphQL gateway.
"""

from django.urls import path

from . import views

app_name = "graphql_gateway"

urlpatterns = [
    # GraphQL Gateway
    path("graphql/", views.GraphQLGatewayView.as_view(), name="graphql_gateway"),
    # Health check
    path("graphql/health/", views.graphql_gateway_health, name="graphql_health"),
    # Introspection
    path(
        "graphql/introspection/",
        views.graphql_introspection,
        name="graphql_introspection",
    ),
]
