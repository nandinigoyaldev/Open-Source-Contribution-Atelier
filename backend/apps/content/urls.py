from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DraftRestoreView,
    LearningPathViewSet,
    LessonDraftViewSet,
    LessonFeedbackListCreateView,
    LessonFeedbackMetricsView,
    LessonFeedbackRetrieveUpdateDeleteView,
    LessonPDFView,
    LessonViewSet,
    ModuleDraftViewSet,
    OrganizationListView,
    QuizDetailView,
    QuizDraftViewSet,
    RoadmapView,
    SearchView,
    SemanticSearchView,
    UserLessonFeedbackView,
)
from .views_imports import CurriculumImportViewSet

router = DefaultRouter()
router.include_format_suffixes = False
router.register("modules", ModuleDraftViewSet, basename="module-draft")
router.register("lessons", LessonDraftViewSet, basename="lesson-draft")
router.register("quiz-questions", QuizDraftViewSet, basename="quiz-draft")
router.register("published-lessons", LessonViewSet, basename="lesson")
router.register(
    "curriculum-imports", CurriculumImportViewSet, basename="curriculum-import"
)
router.register("learning-paths", LearningPathViewSet, basename="learning-path")

urlpatterns = router.urls + [
    path("drafts/<int:pk>/restore/", DraftRestoreView.as_view(), name="draft-restore"),
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
