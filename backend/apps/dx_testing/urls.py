from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DXTestRunViewSet

router = DefaultRouter()
router.register(r'dx-test-run', DXTestRunViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
