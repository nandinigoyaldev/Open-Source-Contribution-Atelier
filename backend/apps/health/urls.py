"""
URL configuration for health checks.
"""

from django.urls import path

from . import views

app_name = "health"

urlpatterns = [
    path("", views.health_view, name="health"),
    path("ready/", views.health_ready_view, name="health-ready"),
    path("worker-ready/", views.worker_readiness_view, name="worker-ready"),
    path("failover/", views.failover_status_view, name="health-failover"),
    path("live/", views.health_live_view, name="health-live"),
    path("db/", views.db_health_view, name="health-db"),
    path(
        "db/replication-lag/", views.replication_lag_view, name="health-replication-lag"
    ),
]
