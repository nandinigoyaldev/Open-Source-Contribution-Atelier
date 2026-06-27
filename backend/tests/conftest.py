import pytest


@pytest.fixture(autouse=True)
def _disable_auth_throttle(settings):
    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
    rates["auth_signup"] = "10000/hour"
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = rates


@pytest.fixture(autouse=True)
def _configure_celery_test_settings(settings):
    settings.CELERY_BROKER_URL = "memory://"
    settings.CELERY_RESULT_BACKEND = "memory://"
    settings.CELERY_TASK_ALWAYS_EAGER = True
