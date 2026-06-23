from apps.dashboard.views import LeaderboardView
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .version_view import version_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/version/", version_view, name="version"),
    path("api/leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/users/", include("apps.accounts.user_urls")),
    path("api/content/", include("apps.content.urls")),
    path("api/progress/", include("apps.progress.urls")),
    path("api/challenges/", include("apps.challenges.urls")),
    path("api/sandbox/", include("apps.sandbox.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/search/", include("apps.search.urls")),
    path("api/webhooks/", include("apps.webhooks.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
