from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    LessonFeedbackListCreateView,
    LessonFeedbackMetricsView,
    LessonFeedbackRetrieveUpdateDeleteView,
    LessonPDFView,
    LessonViewSet,
    OrganizationListView,
    QuizDetailView,
    RoadmapView,
    SearchView,
    SemanticSearchView,
    UserLessonFeedbackView,
)

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
    path("quizzes/<str:quiz_id>/", QuizDetailView.as_view(), name="quiz-detail"),
    # Lesson Feedback endpoints
    path(
        "lessons/<slug:lesson_slug>/feedback/",
        LessonFeedbackListCreateView.as_view(),
        name="lesson-feedback-list-create",
    ),
    path(
        "lessons/<slug:lesson_slug>/feedback/metrics/",
        LessonFeedbackMetricsView.as_view(),
        name="lesson-feedback-metrics",
    ),
    path(
        "lessons/<slug:lesson_slug>/feedback/my/",
        UserLessonFeedbackView.as_view(),
        name="lesson-feedback-user",
    ),
    path(
        "feedback/<int:pk>/",
        LessonFeedbackRetrieveUpdateDeleteView.as_view(),
        name="lesson-feedback-detail",
    ),
]
