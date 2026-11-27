import json
import threading
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.audit import chain as audit_chain
from apps.audit.chain import (
    GENESIS_HASH,
    compute_hash,
    seal_existing_rows,
    verify_chain,
)
from apps.audit.models import RBAC, AuditChainAnchor, AuditChainHead, AuditEvent
from apps.audit.tasks import archive_audit_events
from apps.rbac.models import Permission, Role, UserRole

pytestmark = pytest.mark.django_db

User = get_user_model()
# Typed as Any, there are no Django stubs for the type checker.
Model: Any = AuditEvent
atomic: Any = transaction.atomic
Events: Any = AuditEvent._default_manager
# Goes around the model, the way somebody editing the database would.
Raw: Any = AuditEvent._base_manager


def make_event(number=1, **overrides):
    values = {
        "action": "created",
        "resource_type": "test.chain",
        "resource_id": str(number),
        "after": {"number": number},
        **overrides,
    }
    return Events.create(**values)


def make_events(count):
    return [make_event(number) for number in range(1, count + 1)]


def make_user(username):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="pw-123456789"
    )


def problems(**kwargs):
    return verify_chain(AuditEvent, **kwargs).errors


def head():
    return AuditChainHead._default_manager.get(chain="audit")


# ── Writing ───────────────────────────────────────────────────────────────────


def test_rows_link_to_the_one_before():
    first, second, third = make_events(3)

    assert [second.sequence, third.sequence] == [
        first.sequence + 1,
        first.sequence + 2,
    ]
    assert second.previous_hash == first.hash
    assert third.previous_hash == second.hash
    assert (head().last_sequence, head().head_hash) == (third.sequence, third.hash)
    assert problems() == []


def test_first_row_starts_from_the_genesis_hash():
    Raw.all().delete()
    AuditChainHead._default_manager.filter(chain="audit").delete()

    event = make_event()

    assert (event.sequence, event.previous_hash) == (1, GENESIS_HASH)
    assert problems() == []


def test_caller_cannot_choose_the_chain_columns():
    event = make_event(sequence=999, hash="f" * 64, previous_hash="e" * 64, actor_ref=7)

    assert event.sequence != 999
    assert event.hash != "f" * 64
    assert event.actor_ref is None
    assert problems() == []


def test_values_that_the_database_rewrites_still_verify():
    actor = make_user("roundtrip")
    make_event(
        actor_id=str(actor.pk),
        before={},
        after={
            "whole": 1e20,
            "float": 0.1,
            "list": [1.0, -0.0, {"none": None}],
            "text": "naïve ✓",
            5: "integer key",
        },
        ip_address="2001:DB8::0001",
        extra={"nested": {"b": 2, "a": 1}},
    )
    make_event(ip_address="", before=None, after=None)
    make_event(ip_address="::ffff:10.0.0.1")

    assert problems() == []


def test_proxy_model_writes_to_the_same_chain():
    first = make_event()
    second = RBAC._default_manager.create(
        action="updated", resource_type="User", resource_id="1", extra={"rbac": True}
    )

    assert second.previous_hash == first.hash
    assert problems() == []


def test_bulk_create_is_chained():
    first = make_event()
    events = Events.bulk_create(
        [
            AuditEvent(action="updated", resource_type="User", resource_id=str(i))
            for i in range(3)
        ],
        batch_size=2,
    )

    assert [event.sequence for event in events] == [
        first.sequence + offset for offset in (1, 2, 3)
    ]
    assert events[0].previous_hash == first.hash
    assert head().head_hash == events[-1].hash
    assert problems() == []


def test_empty_bulk_create_leaves_the_head_alone():
    make_event()
    before = head().last_sequence

    assert Events.bulk_create([]) == []
    assert head().last_sequence == before


def test_bulk_create_refuses_conflict_handling():
    with pytest.raises(ValueError):
        Events.bulk_create(
            [AuditEvent(action="created", resource_type="x", resource_id="1")],
            ignore_conflicts=True,
        )


def test_rbac_signals_write_chained_rows():
    user = make_user("rbac-user")
    role = Role.objects.create(name="chain-role")
    role.permissions.add(Permission.objects.create(slug="chain.read"))

    UserRole.objects.create(user=user, role=role)

    assert Events.filter(extra__rbac=True, sequence__isnull=False).exists()
    assert problems() == []


def test_failed_insert_does_not_use_up_a_position():
    last = make_event()

    with pytest.raises(IntegrityError):
        make_event(action=None)

    assert head().last_sequence == last.sequence
    assert make_event(2).previous_hash == last.hash
    assert problems() == []


def test_a_writer_with_a_stale_head_cannot_fork_the_chain():
    first, second = make_events(2)
    # What a second writer would see if it had read the head before ``second``.
    AuditChainHead._default_manager.filter(chain="audit").update(
        last_sequence=first.sequence, head_hash=first.hash
    )

    with pytest.raises(IntegrityError):
        make_event(3)

    assert list(Raw.filter(previous_hash=first.hash)) == [second]


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="needs row locks; SQLite lets only one writer in at a time anyway",
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_writers_take_turns():
    first_is_holding, release = threading.Event(), threading.Event()
    errors = []

    def write(number, hold):
        try:
            with atomic():
                make_event(number)
                if hold:
                    first_is_holding.set()
                    release.wait(10)
        except Exception as error:  # surfaced by the assert below
            errors.append(error)
        finally:
            connection.close()

    make_event(0)
    first = threading.Thread(target=write, args=(1, True))
    second = threading.Thread(target=write, args=(2, False))
    first.start()
    assert first_is_holding.wait(10)
    second.start()
    second.join(1)
    assert second.is_alive(), "the second writer did not wait for the first"
    release.set()
    first.join(10)
    second.join(10)

    assert errors == []
    rows = list(Raw.order_by("sequence"))
    assert [row.resource_id for row in rows] == ["0", "1", "2"]
    assert rows[2].previous_hash == rows[1].hash
    assert problems() == []


# ── The application cannot edit rows ──────────────────────────────────────────


def test_queryset_update_is_refused():
    event = make_event()

    with pytest.raises(PermissionError):
        Events.filter(pk=event.pk).update(resource_id="other")
    with pytest.raises(PermissionError):
        Events.filter(pk=event.pk).update(actor_id=1)
    event.resource_id = "other"
    # bulk_update marks its transaction as broken when it raises.
    with pytest.raises(PermissionError), atomic():
        Events.bulk_update([event], ["resource_id"])

    assert problems() == []


def test_detaching_the_actor_keeps_the_chain_valid():
    actor = make_user("leaver")
    event = make_event(actor=actor)

    assert Events.filter(actor=actor).update(actor=None) == 1

    event.refresh_from_db()
    assert (event.actor_id, event.actor_ref) == (None, actor.pk)
    assert problems() == []


# ── Tampering ─────────────────────────────────────────────────────────────────

TAMPERED_VALUES = {
    "action": "deleted",
    "resource_type": "test.other",
    "resource_id": "999",
    "before": {"forged": True},
    "after": {"number": 20},
    "correlation_id": "forged",
    "ip_address": "10.9.9.9",
    "user_agent": "forged",
    "created_at": timezone.now() - timedelta(days=3),
    "extra": {"forged": True},
    "actor_ref": 4242,
    "sequence": 5000,
    "previous_hash": "a" * 64,
    "hash": "b" * 64,
}


@pytest.mark.parametrize("column", sorted(TAMPERED_VALUES))
def test_editing_any_column_of_an_old_row_is_reported(column):
    _first, target, _last = make_events(3)

    Raw.filter(pk=target.pk).update(**{column: TAMPERED_VALUES[column]})

    assert problems()


def test_every_column_is_covered_by_the_hash():
    spec = AuditEvent.chain
    columns = {field.name for field in Model._meta.concrete_fields}
    covered = set(spec.fields) | {name for pair in spec.refs for name in pair}

    assert columns - covered == {"id", "sequence", "previous_hash", "hash"}


def test_report_names_the_edited_record():
    _first, target, _last = make_events(3)

    Raw.filter(pk=target.pk).update(after={"number": 20})

    assert problems() == [
        f"record {target.sequence} (id {target.pk}): content does not match its hash"
    ]


def test_pointing_a_row_at_another_user_is_reported():
    actor, scapegoat = make_user("real"), make_user("scapegoat")
    event = make_event(actor=actor)

    Raw.filter(pk=event.pk).update(actor=scapegoat)

    assert "actor was changed" in problems()[0]


def test_edit_with_a_recomputed_hash_breaks_the_next_link():
    _first, target, last = make_events(3)
    target.resource_id = "forged"
    Raw.filter(pk=target.pk).update(
        resource_id="forged", hash=compute_hash(AuditEvent.chain, target)
    )

    assert problems() == [
        f"record {last.sequence} (id {last.pk}): does not link to the record before it"
    ]


def test_deleting_a_row_is_reported():
    _first, target, _last = make_events(3)

    Raw.filter(pk=target.pk).delete()

    assert f"record {target.sequence} is missing" in problems()


def test_deleting_the_newest_rows_is_reported():
    _first, second, third = make_events(3)

    Raw.filter(pk__in=[second.pk, third.pk]).delete()

    assert f"records {second.sequence}-{third.sequence} are missing" in problems()


def test_row_written_around_the_model_is_reported():
    make_event()
    Raw.bulk_create(
        [AuditEvent(action="created", resource_type="test", resource_id="planted")]
    )

    assert "is not chained" in problems()[0]


def test_row_appended_without_moving_the_head_is_reported():
    last = make_event()
    planted = AuditEvent(action="created", resource_type="test", resource_id="planted")
    audit_chain.seal(AuditEvent.chain, planted, last.sequence + 1, last.hash)
    Raw.bulk_create([planted])

    assert (
        f"there are records after the chain head, up to {planted.sequence}"
        in problems()
    )


def test_cutting_off_the_end_and_rewinding_the_head_is_reported():
    first, second = make_events(2)
    Raw.filter(pk=second.pk).delete()
    AuditChainHead._default_manager.filter(chain="audit").update(
        last_sequence=first.sequence, head_hash=first.hash
    )

    assert "head signature does not match" in problems()[0]

    # The next real event must not make the forged head look genuine.
    make_event(3)
    assert head().signature == ""
    assert "head signature does not match" in problems()[0]


def test_removing_the_head_is_reported_and_stays_reported():
    make_events(2)
    AuditChainHead._default_manager.filter(chain="audit").delete()

    assert "the chain head is missing" in problems()

    make_event(3)
    assert "head signature does not match" in problems()[0]


def test_checkpoint_catches_history_signed_again_with_the_key():
    first, second = make_events(2)
    checkpoint = (second.sequence, second.hash)
    assert problems(expected=[checkpoint]) == []

    Raw.filter(pk=second.pk).delete()
    AuditChainHead._default_manager.filter(chain="audit").update(
        last_sequence=first.sequence,
        head_hash=first.hash,
        signature=audit_chain.sign(
            *audit_chain.head_parts("audit", first.sequence, first.hash)
        ),
    )

    assert problems() == []
    assert "cannot be confirmed" in problems(expected=[checkpoint])[0]

    replacement = make_event(99)
    assert replacement.sequence == second.sequence
    assert "history was rewritten" in problems(expected=[checkpoint])[0]


def test_old_signing_key_still_verifies_after_rotation(settings):
    settings.AUDIT_CHAIN_KEY = ""
    make_event()
    old_key = settings.SECRET_KEY

    settings.SECRET_KEY = "rotated-" * 8
    assert "head signature does not match" in problems()[0]

    settings.AUDIT_CHAIN_KEY = old_key
    make_event(2)
    assert problems() == []


# ── Retention ─────────────────────────────────────────────────────────────────


@pytest.fixture
def retention(settings, tmp_path):
    settings.AUDIT_RETENTION_DAYS = 30
    settings.AUDIT_ARCHIVE_DIR = tmp_path
    Raw.all().delete()
    AuditChainHead._default_manager.filter(chain="audit").delete()
    return tmp_path


def old():
    return timezone.now() - timedelta(days=60)


def test_chain_verifies_after_retention(retention):
    first = make_event(1, created_at=old())
    second = make_event(2, created_at=old())
    kept = make_event(3)

    assert archive_audit_events() == 2

    anchor = AuditChainAnchor._default_manager.get()
    assert (anchor.first_sequence, anchor.last_sequence) == (1, 2)
    assert (anchor.previous_hash, anchor.last_hash) == (GENESIS_HASH, second.hash)
    assert kept.previous_hash == anchor.last_hash
    assert problems(expected=[(2, second.hash), (3, kept.hash)]) == []
    assert "cannot be confirmed" in problems(expected=[(1, first.hash)])[0]
    (archive,) = retention.glob("audit_archive_*.json")
    assert anchor.archive_file == str(archive)
    assert [row["hash"] for row in json.loads(archive.read_text())] == [
        second.hash,
        first.hash,
    ]


def test_old_rows_between_newer_ones_get_their_own_anchors(retention):
    for number, created_at in enumerate(
        [old(), timezone.now(), old(), old(), timezone.now(), old()], start=1
    ):
        make_event(number, created_at=created_at)

    assert archive_audit_events() == 4
    assert list(
        AuditChainAnchor._default_manager.order_by("first_sequence").values_list(
            "first_sequence", "last_sequence"
        )
    ) == [(1, 1), (3, 4), (6, 6)]
    assert problems() == []


def test_repeated_retention_and_new_events_still_verify(retention, monkeypatch):
    monkeypatch.setattr("apps.audit.tasks._DELETE_BATCH_SIZE", 2)
    for number in range(1, 6):
        make_event(number, created_at=old())
    assert archive_audit_events() == 5
    assert Raw.count() == 0
    assert problems() == []

    event = make_event(6, created_at=old())
    assert event.sequence == 6
    # A second run in the same second must not matter to the anchors.
    assert archive_audit_events() == 1
    assert problems() == []


def test_retention_keeps_a_tampered_row_as_evidence(retention):
    events = [make_event(number, created_at=old()) for number in (1, 2, 3)]
    Raw.filter(pk=events[1].pk).update(resource_id="forged")

    assert archive_audit_events() == 2

    assert list(Raw.values_list("pk", flat=True)) == [events[1].pk]
    assert problems() == [
        f"record 2 (id {events[1].pk}): content does not match its hash"
    ]


def test_retention_does_not_hide_an_earlier_deletion(retention):
    events = [make_event(number, created_at=old()) for number in (1, 2, 3)]
    Raw.filter(pk=events[1].pk).delete()

    assert archive_audit_events() == 2
    assert problems() == ["record 2 is missing"]


def test_forged_anchor_does_not_explain_a_deletion(retention):
    first, second, _third = make_events(3)
    Raw.filter(pk=second.pk).delete()
    AuditChainAnchor._default_manager.create(
        chain="audit",
        first_sequence=2,
        last_sequence=2,
        previous_hash=first.hash,
        last_hash=second.hash,
        signature="0" * 64,
    )

    assert problems() == ["pruned range 2-2: signature does not match"]


def test_removing_an_anchor_is_reported(retention):
    make_event(1, created_at=old())
    make_event(2)
    archive_audit_events()
    AuditChainAnchor._default_manager.all().delete()

    assert problems() == ["record 1 is missing"]


def test_failed_delete_rolls_the_anchors_back(retention, monkeypatch):
    make_event(1, created_at=old())

    def explode(self):
        raise RuntimeError("database went away")

    monkeypatch.setattr("apps.audit.chain.ChainedQuerySet.delete", explode)
    with pytest.raises(RuntimeError):
        archive_audit_events()

    assert Raw.count() == 1
    assert not AuditChainAnchor._default_manager.exists()
    assert problems() == []


# ── Existing rows and the command ─────────────────────────────────────────────


def test_existing_rows_are_sealed_oldest_first(retention):
    now = timezone.now()
    Raw.bulk_create(
        [
            AuditEvent(
                action="created",
                resource_type="legacy",
                resource_id=str(age),
                created_at=now - timedelta(days=age),
            )
            for age in (1, 3, 2)
        ]
    )

    seal_existing_rows(AuditEvent.chain, AuditEvent, AuditChainHead, "default")

    assert list(Raw.order_by("sequence").values_list("resource_id", flat=True)) == [
        "3",
        "2",
        "1",
    ]
    assert problems() == []
    assert make_event(4).sequence == 4
    assert problems() == []


def test_command_prints_checkpoints_that_it_accepts():
    make_events(2)
    out = StringIO()

    call_command("verify_audit_chain", stdout=out)

    assert "audit: OK" in out.getvalue()
    assert "moderation: OK" in out.getvalue()
    checkpoints = [
        line.split()[1]
        for line in out.getvalue().splitlines()
        if line.startswith("checkpoint ")
    ]
    assert len(checkpoints) == 2
    call_command(
        "verify_audit_chain",
        *[f"--expect={value}" for value in checkpoints],
        stdout=StringIO(),
    )


def test_command_fails_and_lists_the_problem():
    _first, target = make_events(2)
    Raw.filter(pk=target.pk).update(resource_id="forged")
    err = StringIO()

    with pytest.raises(CommandError, match="audit"):
        call_command(
            "verify_audit_chain", "--chain=audit", stdout=StringIO(), stderr=err
        )

    assert f"record {target.sequence} (id {target.pk})" in err.getvalue()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--expect=audit:1"],
        ["--expect=other:1:" + "a" * 64],
        ["--expect=audit:one:" + "a" * 64],
        ["--chain=moderation", "--expect=audit:1:" + "a" * 64],
    ],
)
def test_command_rejects_bad_checkpoints(arguments):
    with pytest.raises(CommandError):
        call_command("verify_audit_chain", *arguments, stdout=StringIO())
