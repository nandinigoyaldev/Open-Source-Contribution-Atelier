from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IssueViewSet, ModelViewSet

router = DefaultRouter()
router.register(r'issue', IssueViewSet)
router.register(r'model', ModelViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
