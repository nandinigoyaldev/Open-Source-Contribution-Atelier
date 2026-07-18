from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PortfolioTemplateViewSet, GeneratedPortfolioViewSet

router = DefaultRouter()
router.register(r"templates", PortfolioTemplateViewSet, basename="portfolio-template")
router.register(r"reports", GeneratedPortfolioViewSet, basename="portfolio-report")

urlpatterns = [
    path("", include(router.urls)),
]
