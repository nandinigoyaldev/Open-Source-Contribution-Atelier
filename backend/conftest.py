import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

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


# ---------------------------------------------------------------------------
# Tenant fixtures: two organizations, each with one member user.
# ---------------------------------------------------------------------------


@pytest.fixture
def org_a(db):
    from apps.organizations.models import Organization

    return Organization.objects.create(name="Org A")


@pytest.fixture
def org_b(db):
    from apps.organizations.models import Organization

    return Organization.objects.create(name="Org B")


def _create_tenant_member(username, organization):
    from apps.organizations.models import OrganizationMembership

    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password="pw123456"
    )
    # Profile is auto-created by signal in apps.accounts; set the org.
    profile = getattr(user, "user_profile", None)
    if profile is None:
        from apps.accounts.models import UserProfile

        profile = UserProfile.objects.create(user=user)
    profile.organization = organization
    profile.save()
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.ROLE_MEMBER,
    )
    return user


@pytest.fixture
def user_a(db, org_a):
    return _create_tenant_member("alice", org_a)


@pytest.fixture
def user_b(db, org_b):
    return _create_tenant_member("bob", org_b)


@pytest.fixture
def authed_client_a(api_client, user_a):
    api_client.force_authenticate(user=user_a)
    return api_client


@pytest.fixture
def authed_client_b(api_client, user_b):
    api_client.force_authenticate(user=user_b)
    return api_client


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
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "atelier-test-cache",
        },
    }
    # LocMemCache stores survive database rollback and settings overrides.
    # Keep real throttles enabled, but do not inherit another test's requests.
    from django.core.cache import caches

    caches["default"].clear()
    yield
    caches["default"].clear()


@pytest.fixture(autouse=True)
def _configure_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


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

    original_delay = invalidate_tag_task.delay
    invalidate_tag_task.delay = lambda *args, **kwargs: invalidate_tag_task(
        *args, **kwargs
    )
    yield
    invalidate_tag_task.delay = original_delay
