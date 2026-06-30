from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import LessonViewSet, SearchView, RoadmapView

router = DefaultRouter()
router.include_format_suffixes = False
router.register("lessons", LessonViewSet, basename="lesson")

urlpatterns = router.urls + [
    path("search/", SearchView.as_view(), name="search"),
    path("roadmap/", RoadmapView.as_view(), name="roadmap"),
]
