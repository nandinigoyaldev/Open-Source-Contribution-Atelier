from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from graphene_django.views import GraphQLView

from apps.dashboard.views import LeaderboardView

from .health_view import health_view
from .version_view import version_view

urlpatterns = [
    # ── Admin ──────────────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),
    path("", include("django_prometheus.urls")),
    # ── Health Checks ──────────────────────────────────────────────────────────
    path("health/", include("apps.health.urls")),
    # ── Legacy Health (keep for backward compatibility) ──────────────────────
    path("health/legacy/", health_view, name="health"),
    # ── API Version ────────────────────────────────────────────────────────────
    path("api/version/", version_view, name="version"),
    # ── Leaderboard ────────────────────────────────────────────────────────────
    path("api/leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    # ── Authentication ─────────────────────────────────────────────────────────
    path("accounts/", include("allauth.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/users/", include("apps.accounts.user_urls")),
    # ── Core Apps ──────────────────────────────────────────────────────────────
    path("api/content/", include("apps.content.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/progress/", include("apps.progress.urls")),
    path("api/localization/", include("apps.localization.urls")),
    path("api/challenges/", include("apps.challenges.urls")),
    path("api/sandbox/", include("apps.sandbox.urls")),
    path("api/gamification/", include("apps.gamification.urls")),
    # ── Notifications & Real-time ─────────────────────────────────────────────
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/chat/", include("apps.chat.urls")),
    # ── Search & Collaboration ────────────────────────────────────────────────
    path("api/search/", include("apps.search.urls")),
    path("api/notes/", include("apps.notes.urls")),
    path("api/recommendations/", include("apps.recommendations.urls")),
    # ── Webhooks & Uploads ─────────────────────────────────────────────────────
    path("api/webhooks/", include("apps.webhooks.urls")),
    path("api/uploads/", include("apps.uploads.urls")),
    # ── RBAC ───────────────────────────────────────────────────────────────────
    path("api/rbac/", include("apps.rbac.urls")),
    # ── Additional Apps ────────────────────────────────────────────────────────
    path("api/moderation/", include("apps.moderation.urls")),
    path("api/portfolio/", include("apps.portfolio.urls")),
    path("api/organizations/", include("apps.organizations.urls")),
    # ── Events & GraphQL ──────────────────────────────────────────────────────
    # path("api/events/", include("apps.events.urls")),
    path("api/graphql/", include("apps.graphql_gateway.urls")),
    path("api/graphql/legacy/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    # ── API Documentation ──────────────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),  # Fixed here
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc-ui",
    ),
    # ── GraphQL ────────────────────────────────────────────────────────────────
    path("api/graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
]

# ── Development URLs ──────────────────────────────────────────────────────────
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    from apps.feature_flags.debug_view import feature_flags_debug_view

    urlpatterns += [
        path("api/organizations/", include("apps.organizations.urls")),
        path("api/feature-flags/", include("apps.feature_flags.urls")),
        path(
            "debug/feature-flags/", feature_flags_debug_view, name="debug-feature-flags"
        ),
        path(
            "api/feature-flags/debug/",
            feature_flags_debug_view,
            name="feature-flags-debug",
        ),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
