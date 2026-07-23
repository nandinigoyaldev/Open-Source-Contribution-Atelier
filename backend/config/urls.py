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
from apps.billing.views import CheckoutSessionView
from apps.billing.webhooks import stripe_webhook

urlpatterns = [
    # ── Admin ──────────────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),
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
    path("api/predictions/", include("apps.predictions.urls")),
    path("create-checkout-session/", CheckoutSessionView.as_view()),
    path("webhook/", stripe_webhook),
    path("api/search/", include("apps.search.urls")),
    path("api/notes/", include("apps.notes.urls")),
    path("api/recommendations/", include("apps.recommendations.urls")),
    # ============================================================
    # WEBHOOKS & UPLOADS
    # ============================================================
    path("api/uploads/", include("apps.uploads.urls")),
    # ── RBAC ───────────────────────────────────────────────────────────────────
    path("api/rbac/", include("apps.rbac.urls")),
    # ── Additional Apps ────────────────────────────────────────────────────────
    path("api/moderation/", include("apps.moderation.urls")),
    path("api/portfolio/", include("apps.portfolio.urls")),
    path("api/organizations/", include("apps.organizations.urls")),
    path("api/accessibility/", include("apps.accessibility.urls")),
    # ── Issue Reporting ────────────────────────────────────────────────────────
    path("api/issues/", include("apps.issues.urls")),
    # ── Project Health & Security ─────────────────────────────────────────────
    path("api/project-health/", include("apps.project_health.urls")),
    path("api/security/", include("apps.security.urls")),
    # ── Plugins ────────────────────────────────────────────────────────────────
    path("api/plugins/", include("apps.plugins.urls")),
    # ── Scaffolded Apps ────────────────────────────────────────────────────────
    path("api/burnout-detection/", include("apps.burnout_detection.urls")),
    path("api/advanced-search/", include("apps.advanced_search.urls")),
    path("api/feature-requests/", include("apps.feature_requests.urls")),
    path("api/issue-categorization/", include("apps.issue_categorization.urls")),
    path("api/issue-quality-ci/", include("apps.issue_quality_ci.urls")),
    path("api/issue-routing/", include("apps.issue_routing.urls")),
    path("api/onboarding/", include("apps.onboarding.urls")),
    path("api/pr-review-bot/", include("apps.pr_review_bot.urls")),
    path("api/skills-matching/", include("apps.skills_matching.urls")),
    path("api/experiments/", include("apps.experiments.urls")),
    path("api/feed/", include("apps.feed.urls")),
    path("api/dx-testing/", include("apps.dx_testing.urls")),
    path("api/issue-quality/", include("apps.issue_quality.urls")),
    path("api/ml-triage/", include("apps.ml_triage.urls")),
    # ── AI Tutor ────────────────────────────────────────────────────────────────
    path("api/ai/tutor/", include("apps.ai_tutor.urls")),
    # ── Events & GraphQL ──────────────────────────────────────────────────────
    path("api/graphql/", include("apps.graphql_gateway.urls")),
    path("api/graphql/legacy/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    # ============================================================
    # API DOCUMENTATION
    # ============================================================
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
]

# ── Development URLs ──────────────────────────────────────────────────────────
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    from apps.feature_flags.debug_view import feature_flags_debug_view

    urlpatterns += [
        path("api/organizations/", include("apps.organizations.urls")),
        path("api/feature-flags/", include("apps.feature_flags.urls")),
    ]
