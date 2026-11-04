from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from graphene_django.views import GraphQLView

from apps.billing.views import CheckoutSessionView
from apps.billing.webhooks import stripe_webhook
from apps.content.views_notes import LessonNoteAPIView
from apps.dashboard.views import LeaderboardView

from .health_view import health_view
from .version_view import api_versions_view, version_view

api_v1_patterns = [
    # ── Django Admin & External Webhooks ──────────────────────────────────────
    path("admin/", admin.site.urls),
    path("api/admin/audit/", include("apps.audit.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/admin/", include("apps.monitoring.urls")),
    path("api/monitoring/", include("apps.monitoring.urls")),
    path("api/admin/core/", include("apps.core.urls")),
    path("api/admin/db/", include("apps.core.urls")),
    # ── Health Checks ──────────────────────────────────────────────────────────
    path("health/", include("apps.health.urls")),
    path("health/legacy/", health_view, name="health"),
    # ── Version Discovery (root /api/versions/) ─────────────────────────────
    path("version/", version_view, name="version"),
    path("versions/", api_versions_view, name="versions-discovery"),
    path("api/version/", version_view, name="version"),
    path("api/versions/", api_versions_view, name="root-api-versions"),
    # ── Leaderboard ────────────────────────────────────────────────────────────
    path("api/leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    # ── Authentication ─────────────────────────────────────────────────────────
    path("accounts/", include("allauth.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/users/", include("apps.accounts.user_urls")),
    # ── OAuth 2.0 & OpenID Connect ──────────────────────────────────────────────
    path("oauth/", include("apps.oauth.urls")),
    # ── Core Apps ──────────────────────────────────────────────────────────────
    path("api/content/", include("apps.content.urls")),
    path(
        "api/lessons/<str:lesson_id>/notes",
        LessonNoteAPIView.as_view(),
        name="api-lesson-notes",
    ),
    path(
        "api/lessons/<str:lesson_id>/notes/",
        LessonNoteAPIView.as_view(),
        name="api-lesson-notes-slash",
    ),
    path("api/billing/", include("apps.billing.urls")),
    path("api/progress/", include("apps.progress.urls")),
    path("api/localization/", include("apps.localization.urls")),
    path("api/challenges/", include("apps.challenges.urls")),
    path("api/sandbox/", include("apps.sandbox.urls")),
    path("api/gamification/", include("apps.gamification.urls")),
    # ── Notifications & Real-time ─────────────────────────────────────────────
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/exports/", include("apps.data_exports.urls")),
    path("api/chat/", include("apps.chat.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/errors/", include("apps.errors.urls")),
    path("api/predictions/", include("apps.predictions.urls")),
    path("create-checkout-session/", CheckoutSessionView.as_view()),
    path("webhook/", stripe_webhook),
    path("api/search/", include("apps.search.urls")),
    path("api/notes/", include("apps.notes.urls")),
    path("api/recommendations/", include("apps.recommendations.urls")),
    # ============================================================
    # WEBHOOKS & UPLOADS
    # ============================================================
    path("api/webhooks/", include("apps.webhooks.urls")),
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
    path("api/project-health/", include("apps.project_health.urls")),
    path("api/security/", include("apps.security.urls")),
    path("api/flashcards/", include("apps.flashcards.urls", namespace="flashcards")),
    path(
        "api/learning-analytics/",
        include("apps.learning_analytics.urls", namespace="learning_analytics"),
    ),
    path(
        "api/learning-journal/",
        include("apps.learning_journal.urls", namespace="learning_journal"),
    ),
    path(
        "api/study-groups/", include("apps.study_groups.urls", namespace="study_groups")
    ),
    path("api/mentorship/", include("apps.mentorship.urls", namespace="mentorship")),
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
    path("api/dx-analytics/", include("apps.dx_analytics.urls")),
    path("api/issue-quality/", include("apps.issue_quality.urls")),
    path("api/ml-triage/", include("apps.ml_triage.urls")),
    # ── AI Tutor ────────────────────────────────────────────────────────────────
    path("api/ai/tutor/", include("apps.ai_tutor.urls")),
    path("", include("apps.oauth.urls")),
    # ── Events & GraphQL ──────────────────────────────────────────────────────
    path("api/events/", include("apps.events.urls")),
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
]

urlpatterns = [
    path("api/versions/", api_versions_view, name="root-api-versions"),
    path("api/v1/", include(api_v1_patterns)),
    path("", include(api_v1_patterns)),
]
if settings.DEBUG:
    from apps.feature_flags.debug_view import feature_flags_debug_view

    urlpatterns += [
        path("api/v1/feature-flags/", include("apps.feature_flags.urls")),
        path("api/feature-flags/", include("apps.feature_flags.urls")),
        path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    ]
