import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    user = User.objects.filter(username="testuser").first()
    if user:
        return user
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpassword123",
    )


@pytest.fixture(autouse=True)
def _disable_auth_throttle(settings):
    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
    rates["auth_signup"] = "10000/hour"
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = rates


@pytest.fixture(autouse=True)
def _configure_django_q_test_settings(settings):
    settings.Q_CLUSTER = {
        "sync": True,
        "orm": "default",
    }
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }


@pytest.fixture(autouse=True)
def mock_django_q_async_task(monkeypatch):
    """
    Globally mock django_q's async_task to avoid running into Redis connection issues
    during tests that trigger events (e.g. User post_save/post_delete).
    """
    import django_q.tasks
    monkeypatch.setattr(django_q.tasks, "async_task", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def mock_event_bus_dispatch(monkeypatch):
    """
    Globally mock EventBus.dispatch to avoid triggering background tasks during tests.
    """
    from apps.events.services.event_bus import EventBus
    monkeypatch.setattr(EventBus, "dispatch", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _configure_celery_test_settings(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_ALWAYS_EAGER = True
    from apps.core.tasks import invalidate_tag_task
    invalidate_tag_task.delay = lambda *args, **kwargs: invalidate_tag_task(*args, **kwargs)

