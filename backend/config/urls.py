from django.contrib import admin
from django.urls import path, include, re_path
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from graphene_django.views import GraphQLView
from django.urls import path, include

from apps.dashboard.views import LeaderboardView

from .health_view import health_view
from .version_view import version_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_prometheus.urls")),
    path("health/", health_view, name="health"),
    path("api/version/", version_view, name="version"),
    path("api/leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("accounts/", include("allauth.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/users/", include("apps.accounts.user_urls")),
    path("", include("django_prometheus.urls")),
    path("api/content/", include("apps.content.urls")),
    path("api/progress/", include("apps.progress.urls")),
    path("api/challenges/", include("apps.challenges.urls")),
    path("api/sandbox/", include("apps.sandbox.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/search/", include("apps.search.urls")),
    path("api/webhooks/", include("apps.webhooks.urls")),
    path("api/notes/", include("apps.notes.urls")),
    path("api/chat/", include("apps.chat.urls")),
    path("api/recommendations/", include("apps.recommendations.urls")),
    # ============================================================
    # WEBHOOKS & UPLOADS
    # ============================================================
    path("api/webhooks/", include("apps.webhooks.urls")),
    path("api/uploads/", include("apps.uploads.urls")),
    # ============================================================
    # RBAC (Role-Based Access Control)
    # ============================================================
    path("api/rbac/", include("apps.rbac.urls")),
    # ============================================================
    # DOMAIN EVENTS
    # ============================================================
    # path("api/events/", include("apps.events.urls")),
    # ============================================================
    # GRAPHQL FEDERATION GATEWAY
    # ============================================================
    # path("api/graphql/", include("apps.graphql_gateway.urls")),
    # ============================================================
    # LEGACY GRAPHQL (Keep for backward compatibility)
    # ============================================================
    path("api/graphql/legacy/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    # ============================================================
    # API DOCUMENTATION
    # ============================================================
    path("api/rbac/", include("apps.rbac.urls")),
    path("api/uploads/", include("apps.uploads.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # ============================================================
    # PROMETHEUS METRICS
    # ============================================================
    path("api/graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    path("", include("django_prometheus.urls")),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    from apps.feature_flags.debug_view import feature_flags_debug_view

    urlpatterns += [
        path("api/organizations/", include("apps.organizations.urls")),
        path("api/feature-flags/", include("apps.feature_flags.urls")),
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    ]
