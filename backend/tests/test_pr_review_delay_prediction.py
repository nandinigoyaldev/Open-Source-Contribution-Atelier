import pytest
from rest_framework.test import APIClient
from apps.predictions.models import ReviewerAvailability, PullRequestMetric, ReviewDelayPrediction, DelayAlert
from apps.predictions.ml_engine import predictor
from apps.predictions.tasks import monitor_pr_review_delays, update_reviewer_availability


@pytest.mark.django_db
class TestPRReviewDelayPrediction:

    def setup_method(self):
        self.client = APIClient()

    def test_ml_engine_prediction_confidence_and_risk(self):
        """
        Verify ML engine computes predicted review delay with ±12h confidence interval and accurate risk levels.
        """
        # Low risk scenario (small PR, available reviewer)
        res_low = predictor.predict(
            additions=30, deletions=10, changed_files=2,
            current_workload=0, activity_score=1.0, avg_response_time_hours=12.0
        )
        assert res_low["confidence_interval_hours"] == 12.0
        assert res_low["predicted_delay_hours"] >= 0.0
        assert res_low["risk_level"] in ["LOW", "MEDIUM"]

        # High risk scenario (large PR, heavy reviewer workload)
        res_high = predictor.predict(
            additions=1500, deletions=400, changed_files=25,
            current_workload=6, activity_score=0.2, avg_response_time_hours=72.0
        )
        assert res_high["confidence_interval_hours"] == 12.0
        assert res_high["predicted_delay_hours"] > 48.0
        assert res_high["risk_level"] in ["HIGH", "CRITICAL"]

    def test_reviewer_availability_tracking(self):
        """
        Verify tracking of reviewer workload and activity score.
        """
        reviewer = ReviewerAvailability.objects.create(
            reviewer_username="lead_reviewer",
            current_workload=2,
            activity_score=0.9,
            avg_response_time_hours=18.0,
        )
        assert reviewer.current_workload == 2

        pr = PullRequestMetric.objects.create(
            pr_number=101,
            title="Complex Refactoring",
            author="dev1",
            assigned_reviewer=reviewer,
            additions=300,
            deletions=150,
            changed_files=8,
            status="OPEN",
        )
        assert pr.assigned_reviewer == reviewer

        update_reviewer_availability()
        reviewer.refresh_from_db()
        assert reviewer.current_workload == 1

    def test_automated_delay_alerts_generation(self):
        """
        Verify periodic monitoring task generates automated alerts for high risk PRs.
        """
        reviewer = ReviewerAvailability.objects.create(
            reviewer_username="busy_maintainer",
            current_workload=5,
            activity_score=0.3,
            avg_response_time_hours=60.0,
        )

        PullRequestMetric.objects.create(
            pr_number=202,
            title="Massive Architectural Overhaul",
            author="contributor2",
            assigned_reviewer=reviewer,
            additions=2500,
            deletions=900,
            changed_files=35,
            status="OPEN",
        )

        results = monitor_pr_review_delays()
        assert results["predictions_processed"] >= 1
        assert results["alerts_created"] >= 1

        alert = DelayAlert.objects.filter(prediction__pr__pr_number=202).first()
        assert alert is not None
        assert alert.is_sent is True
        assert "High Stagnation Risk" in alert.message or "CRITICAL" in alert.alert_type or "HIGH" in alert.alert_type

    def test_predict_api_endpoint(self):
        """
        Test POST /api/predictions/predict/ API endpoint.
        """
        payload = {
            "pr_number": 303,
            "title": "Add PR Review Predictor",
            "additions": 450,
            "deletions": 80,
            "changed_files": 6,
            "assigned_reviewer": "test_reviewer",
            "current_workload": 2,
            "activity_score": 0.85,
        }

        response = self.client.post("/api/predictions/predict/", payload, format="json")
        assert response.status_code == 200
        data = response.json()

        assert data["pr_number"] == 303
        assert "predicted_delay_hours" in data
        assert data["confidence_interval_hours"] == 12.0
        assert "risk_level" in data
        assert "recommendation" in data

    def test_reviewer_availability_api_endpoint(self):
        """
        Test GET and POST /api/predictions/reviewers/ API endpoint.
        """
        response = self.client.get("/api/predictions/reviewers/")
        assert response.status_code == 200

        payload = {
            "reviewer_username": "reviewer_alex",
            "current_workload": 3,
            "activity_score": 0.95,
            "avg_response_time_hours": 16.0,
        }
        post_resp = self.client.post("/api/predictions/reviewers/", payload, format="json")
        assert post_resp.status_code == 201
        assert post_resp.json()["reviewer_username"] == "reviewer_alex"

    def test_alerts_and_analytics_api_endpoints(self):
        """
        Test GET /api/predictions/alerts/ and GET /api/predictions/analytics/ API endpoints.
        """
        alerts_resp = self.client.get("/api/predictions/alerts/")
        assert alerts_resp.status_code == 200

        analytics_resp = self.client.get("/api/predictions/analytics/")
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()

        assert "total_prs_tracked" in analytics_data
        assert "confidence_margin_hours" in analytics_data
        assert analytics_data["confidence_margin_hours"] == 12.0
        assert "estimated_review_time_reduction" in analytics_data
