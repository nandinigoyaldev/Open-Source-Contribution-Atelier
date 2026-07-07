import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestMonitoringMetrics:
    def setup_method(self):
        self.client = APIClient()

    def test_metrics_endpoint_is_accessible(self):
        """Ensure Prometheus /metrics endpoint is exposed and reachable."""
        # The prometheus metrics endpoint is normally mapped to /metrics by default in django_prometheus.urls
        response = self.client.get("/metrics")
        assert (
            response.status_code == 200
        ), f"Metrics endpoint returned {response.status_code}"

    def test_metrics_content_format(self):
        """Ensure the metrics endpoint returns Prometheus formatted text."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify it's returning text, not JSON
        assert response["Content-Type"].startswith(
            "text/plain"
        ), "Content type must be text/plain for Prometheus"

        # Check for core Django metrics exposed by django_prometheus
        assert (
            "django_http_requests_before_middlewares_total" in content
        ), "Missing Django HTTP request metrics"
        assert (
            "django_http_responses_before_middlewares_total" in content
        ), "Missing Django HTTP response metrics"

    def test_metrics_db_connection_exposed(self):
        """Ensure database metrics are successfully tracked via the middleware/app."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify database metrics are present in the scrape output
        assert (
            "django_db_query_duration_seconds" in content
            or "django_db_execute_total" in content
        ), "Database query metrics are missing"
