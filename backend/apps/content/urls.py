from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (LessonPDFView, LessonViewSet, OrganizationListView,
                    RoadmapView, SearchView, SemanticSearchView)

router = DefaultRouter()
router.include_format_suffixes = False
router.register("lessons", LessonViewSet, basename="lesson")

urlpatterns = router.urls + [
    path("search/", SearchView.as_view(), name="search"),
    path("semantic-search/", SemanticSearchView.as_view(), name="semantic-search"),
    path("organizations/", OrganizationListView.as_view(), name="organization-list"),
    path("roadmap/", RoadmapView.as_view(), name="roadmap"),
    path(
        "lessons/<int:pk>/pdf/",
        LessonPDFView.as_view(),
        name="lesson-pdf",
    ),
]
