import datetime as dt
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications import tasks
from apps.notifications.digests import queue_weekly_digest
from apps.notifications.models import NotificationPreference

MONDAY = dt.datetime(2026, 11, 9, 8, tzinfo=dt.timezone.utc)


@pytest.fixture
def digest_clock(monkeypatch):
    value = SimpleNamespace(now=MONDAY - dt.timedelta(days=1))
    monkeypatch.setattr(timezone, "now", lambda: value.now)
    return value


@pytest.fixture
def digest_subscriber(settings, digest_clock, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    monkeypatch.setattr(tasks.ChannelRateLimiter, "is_allowed", lambda *a: (True, 0))
    user = get_user_model().objects.create_user(
        username="weekly", email="weekly@example.test"
    )
    profile = user.user_profile
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    pref.digest_frequency = "weekly"
    pref.digest_time = dt.time(8)
    pref.channel_preferences = {
        "badge": {"email": True, "in_app": True},
        "comment": {"email": True, "in_app": True},
    }
    pref.save()
    return pref


@pytest.fixture
def digest_batch(digest_subscriber, digest_clock, django_capture_on_commit_callbacks):
    def run(execute=True):
        with django_capture_on_commit_callbacks(execute=execute):
            return queue_weekly_digest(digest_subscriber.pk, digest_clock.now)

    return run
