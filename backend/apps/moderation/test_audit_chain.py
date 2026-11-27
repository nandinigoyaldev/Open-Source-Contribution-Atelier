from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.deletion_service import execute_account_deletion
from apps.audit.chain import verify_chain
from apps.audit.models import AuditEvent
from apps.moderation.audit_utils import log_moderation_action
from apps.moderation.models import ContentReport, ModerationAuditEvent
from apps.notes.models import Note

pytestmark = pytest.mark.django_db

User = get_user_model()
# Typed as Any, there are no Django stubs for the type checker.
Model: Any = ModerationAuditEvent
Reports: Any = ContentReport._default_manager
Client: Any = APIClient
Events: Any = ModerationAuditEvent._default_manager
Raw: Any = ModerationAuditEvent._base_manager


def make_user(username, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw-123456789",
        **extra,
    )


@pytest.fixture
def people():
    return {
        "reporter": make_user("chain-reporter"),
        "moderator": make_user("chain-moderator", is_staff=True),
        "target": make_user("chain-target"),
    }


def make_report(reporter, object_id=1):
    return Reports.create(
        reporter=reporter,
        content_type=ContentType.objects.get_for_model(User),
        object_id=object_id,
        category=ContentReport.Category.SPAM,
    )


def log(people, report, status="APPROVED"):
    return log_moderation_action(
        content_report=report,
        moderator=people["moderator"],
        target_user=people["target"],
        status_before="PENDING",
        status_after=status,
        reason="spam link",
    )


def problems():
    return verify_chain(ModerationAuditEvent).errors


def test_moderation_events_are_chained(people):
    report = make_report(people["reporter"])
    first, second = log(people, report), log(people, report, "DISMISSED")

    assert second.previous_hash == first.hash
    assert second.sequence == first.sequence + 1
    assert (first.content_report_ref, first.moderator_ref, first.target_user_ref) == (
        report.pk,
        people["moderator"].pk,
        people["target"].pk,
    )
    assert problems() == []


def test_moderation_action_endpoint_writes_a_chained_event(people):
    report = make_report(people["reporter"], object_id=people["target"].pk)
    client = Client()
    client.force_authenticate(user=people["moderator"])

    response = client.post(
        f"/api/moderation/reports/{report.pk}/action/", {"status": "DISMISSED"}
    )

    assert response.status_code == 200
    assert Events.get(content_report=report).hash
    assert problems() == []


TAMPERED_VALUES = {
    "event_type": "REPORT_DISMISSED",
    "status_before": "DISMISSED",
    "status_after": "DISMISSED",
    "action_taken": "REMOVED",
    "reason": "nothing to see",
    "created_at": timezone.now() - timedelta(days=3),
    "content_report_ref": 4242,
    "moderator_ref": 4242,
    "target_user_ref": 4242,
    "sequence": 5000,
    "previous_hash": "a" * 64,
    "hash": "b" * 64,
}


@pytest.mark.parametrize("column", sorted(TAMPERED_VALUES))
def test_editing_any_column_of_an_old_event_is_reported(people, column):
    report = make_report(people["reporter"])
    target = log(people, report)
    log(people, report, "DISMISSED")

    Raw.filter(pk=target.pk).update(**{column: TAMPERED_VALUES[column]})

    assert problems()


def test_every_column_is_covered_by_the_hash():
    spec = ModerationAuditEvent.chain
    columns = {field.name for field in Model._meta.concrete_fields}
    covered = set(spec.fields) | {name for pair in spec.refs for name in pair}

    assert columns - covered == {"id", "sequence", "previous_hash", "hash"}


@pytest.mark.parametrize("key", ["content_report", "moderator", "target_user"])
def test_pointing_an_event_somewhere_else_is_reported(people, key):
    event = log(people, make_report(people["reporter"]))
    other = (
        make_report(people["reporter"], object_id=2)
        if key == "content_report"
        else make_user("chain-other")
    )

    Raw.filter(pk=event.pk).update(**{key: other})

    assert f"{key} was changed" in problems()[0]


def test_deleting_an_event_is_reported(people):
    report = make_report(people["reporter"])
    target = log(people, report)
    log(people, report, "DISMISSED")

    Raw.filter(pk=target.pk).delete()

    assert f"record {target.sequence} is missing" in problems()


def test_events_cannot_be_changed_through_the_model(people):
    event = log(people, make_report(people["reporter"]))

    event.reason = "edited"
    with pytest.raises(PermissionError):
        event.save()
    with pytest.raises(PermissionError):
        event.delete()
    with pytest.raises(PermissionError):
        Events.filter(pk=event.pk).update(reason="edited")

    assert problems() == []


def test_deleting_a_report_keeps_the_event_and_the_chain(people):
    report = make_report(people["reporter"])
    report_id = report.pk
    event = log(people, report)

    report.delete()

    event.refresh_from_db()
    assert (event.content_report_id, event.content_report_ref) == (None, report_id)
    assert problems() == []

    client = Client()
    client.force_authenticate(user=people["moderator"])
    response = client.get("/api/moderation/audit/")
    assert response.status_code == 200
    assert response.data["results"][0]["content_report_id"] == report_id


def test_account_deletion_keeps_both_chains_valid(people):
    note: Any = Note
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(
            cursor, note._meta.db_table
        )
    if "version" not in {column.name for column in columns}:
        # Deleting any user fails while Note is ahead of its migrations.
        # Runs with --nomigrations, or once that migration exists.
        pytest.skip("the notes app is missing a migration")

    reporter, moderator = people["reporter"], people["moderator"]
    # The reporter is also an actor, so deletion has links to cut in both tables.
    audit_event = AuditEvent._default_manager.create(
        actor=reporter, action="created", resource_type="test", resource_id="1"
    )
    event = log(people, make_report(reporter))
    reporter_id, moderator_id = reporter.pk, moderator.pk

    execute_account_deletion(reporter)
    execute_account_deletion(moderator)

    assert not User.objects.filter(pk__in=[reporter_id, moderator_id]).exists()
    audit_event.refresh_from_db()
    event.refresh_from_db()
    assert (audit_event.actor_id, audit_event.actor_ref) == (None, reporter_id)
    assert (event.moderator_id, event.moderator_ref) == (None, moderator_id)
    assert event.content_report_id is None
    assert problems() == []
    assert verify_chain(AuditEvent).errors == []
