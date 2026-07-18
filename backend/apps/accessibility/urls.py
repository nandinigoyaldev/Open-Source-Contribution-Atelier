from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import A11yIssueViewSet

router = DefaultRouter()
router.register(r'issues', A11yIssueViewSet, basename='a11y-issue')

urlpatterns = [
    path('', include(router.urls)),
]
