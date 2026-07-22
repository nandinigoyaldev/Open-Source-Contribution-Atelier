from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExperimentViewSet, ExperimentAssignmentViewSet, ExperimentEventViewSet

router = DefaultRouter()
router.register(r'experiment', ExperimentViewSet)
router.register(r'experiment-assignment', ExperimentAssignmentViewSet)
router.register(r'experiment-event', ExperimentEventViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
