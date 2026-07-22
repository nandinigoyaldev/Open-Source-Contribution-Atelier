from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContributorActivityViewSet, BurnoutSignalViewSet, InterventionViewSet, BurnoutMetricViewSet

router = DefaultRouter()
router.register(r'contributor-activity', ContributorActivityViewSet)
router.register(r'burnout-signal', BurnoutSignalViewSet)
router.register(r'intervention', InterventionViewSet)
router.register(r'burnout-metric', BurnoutMetricViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
