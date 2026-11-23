import json
from datetime import datetime, timedelta, timezone

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.audit.models import AuditEvent
from apps.audit.tasks import archive_audit_events
from config.settings import _parse_audit_retention_days


@pytest.mark.parametrize(("raw", "days"), [(None, 90), ("1", 1), (" 30 ", 30)])
def test_retention_parses_missing_and_positive_values(raw, days):
    assert _parse_audit_retention_days(raw) == days


@pytest.mark.parametrize("raw", ["", "0", "-1", "3.5", "never"])
def test_retention_rejects_invalid_configuration(raw):
    with pytest.raises(ImproperlyConfigured, match="AUDIT_RETENTION_DAYS"):
        _parse_audit_retention_days(raw)


@pytest.mark.django_db
def test_archive_only_deletes_events_strictly_older_than_the_retention_cutoff(
    settings, monkeypatch, tmp_path
):
    settings.AUDIT_RETENTION_DAYS = 30
    settings.AUDIT_ARCHIVE_DIR = tmp_path
    now = datetime(2026, 1, 16, 12, tzinfo=timezone.utc)
    cutoff = now - timedelta(days=30)
    tick = timedelta(microseconds=1)
    for resource_id, created_at in (
        ("older", cutoff - tick),
        ("at-cutoff", cutoff),
        ("newer", cutoff + tick),
    ):
        AuditEvent._default_manager.create(
            action="created",
            resource_type="test.retention",
            resource_id=resource_id,
            created_at=created_at,
        )
    monkeypatch.setattr("apps.audit.tasks.timezone.now", lambda: now)

    assert archive_audit_events() == 1
    assert set(
        AuditEvent._default_manager.filter(resource_type="test.retention").values_list(
            "resource_id", flat=True
        )
    ) == {"at-cutoff", "newer"}
    (archive_file,) = tmp_path.glob("audit_archive_*.json")
    assert [event["resource_id"] for event in json.loads(archive_file.read_text())] == [
        "older"
    ]


@pytest.mark.django_db
def test_retention_longer_than_the_calendar_keeps_events(settings, tmp_path):
    settings.AUDIT_RETENTION_DAYS = 1_000_000_000
    settings.AUDIT_ARCHIVE_DIR = tmp_path
    event = AuditEvent._default_manager.create(
        action="created", resource_type="test.retention", resource_id="keep"
    )

    assert archive_audit_events() == 0
    assert AuditEvent._default_manager.filter(pk=event.pk).exists()
    assert not list(tmp_path.iterdir())
