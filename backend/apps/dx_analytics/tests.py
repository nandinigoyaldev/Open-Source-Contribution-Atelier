import pytest
from apps.dx_analytics.models import DeveloperExperienceMetric, DXSnapshot
from apps.dx_analytics.services import DXScoreService


@pytest.mark.django_db
def test_dx_score_service_perfect():
    # Should be 100 when no failures or slow times
    DeveloperExperienceMetric.objects.create(
        workflow_name="fast_test", execution_time_ms=5000, success=True
    )
    score = DXScoreService.calculate_current_score()
    assert score == 100


@pytest.mark.django_db
def test_dx_score_service_failure_penalty():
    DeveloperExperienceMetric.objects.create(
        workflow_name="failing_test", execution_time_ms=5000, success=False
    )
    score = DXScoreService.calculate_current_score()
    assert score < 100
