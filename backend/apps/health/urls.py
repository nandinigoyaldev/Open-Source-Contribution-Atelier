"""
URL configuration for health checks.
"""

from django.urls import path
from . import views

app_name = "health"

urlpatterns = [
    path("", views.health_view, name="health"),
    path("ready/", views.health_ready_view, name="health-ready"),
    path("live/", views.health_live_view, name="health-live"),
]