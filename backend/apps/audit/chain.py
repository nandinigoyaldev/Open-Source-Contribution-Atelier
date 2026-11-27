"""
Hash chain that makes the audit tables tamper evident.

Each chained row has a position (``sequence``), the hash of the row before it
(``previous_hash``) and its own ``hash``, a SHA-256 over those two and the row's
content. One ``AuditChainHead`` row per chain holds the last position and hash.
A writer updates that row first, so the database makes the next writer wait until
the transaction ends and two rows can never be built on the same predecessor.

The row hashes need no secret. The head and the retention anchors are signed with
``AUDIT_CHAIN_KEY`` (or ``SECRET_KEY``), so database access alone is not enough
to cut off the end of a chain or to pass a deletion off as retention.

See docs/AUDIT_EVENTS.md.
"""

from __future__ import annotations

import hashlib
import heapq
import ipaddress
import json
import logging
from dataclasses import dataclass, field
from datetime import timezone as dt_timezone
from decimal import Decimal
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    cast,
)

from django.apps import apps
from django.conf import settings
from django.db import models, router, transaction
from django.db.models import F, Max, Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

_KEY_SALT = "apps.audit.chain"
_CHUNK_SIZE = 2000
_BACKFILL_BATCH_SIZE = 500


@dataclass(frozen=True)
class ChainSpec:
    """What goes into the hash of one chained table."""

    name: str
    # Concrete columns that are hashed as they are.
    fields: Tuple[str, ...]
    # (foreign key, snapshot column). The snapshot is hashed instead of the key,
    # because the key is set to NULL when the target row is deleted.
    refs: Tuple[Tuple[str, str], ...]


AUDIT_CHAIN = ChainSpec(
    name="audit",
    fields=(
        "action",
        "resource_type",
        "resource_id",
        "before",
        "after",
        "correlation_id",
        "ip_address",
        "user_agent",
        "created_at",
        "extra",
    ),
    refs=(("actor", "actor_ref"),),
)

MODERATION_CHAIN = ChainSpec(
    name="moderation",
    fields=(
        "event_type",
        "status_before",
        "status_after",
        "action_taken",
        "reason",
        "created_at",
    ),
    refs=(
        ("content_report", "content_report_ref"),
        ("moderator", "moderator_ref"),
        ("target_user", "target_user_ref"),
    ),
)


# ── Hashing ───────────────────────────────────────────────────────────────────


def _stable_numbers(value: Any) -> Any:
    # PostgreSQL's jsonb hands 1e20 back as an integer, so whole floats are
    # hashed as integers on the way in and on the way out.
    if isinstance(value, float) and value.is_integer():
        return int(Decimal(repr(value)))
    if isinstance(value, dict):
        return {key: _stable_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable_numbers(item) for item in value]
    return value


def _canonical(model_field: Any, value: Any) -> Any:
    """The value as it will read back from the database, in one fixed form."""
    if value is None:
        return None
    if isinstance(model_field, models.JSONField):
        codec: Any = model_field
        stored = json.dumps(value, cls=codec.encoder)
        return _stable_numbers(json.loads(stored, cls=codec.decoder))
    if isinstance(model_field, models.DateTimeField):
        moment = model_field.to_python(value)
        if timezone.is_naive(moment):
            moment = timezone.make_aware(moment, timezone.get_default_timezone())
        return moment.astimezone(dt_timezone.utc).isoformat()
    if isinstance(model_field, models.GenericIPAddressField):
        # An empty address is stored as NULL.
        if not value:
            return None
        try:
            return ipaddress.ip_address(str(value).strip()).compressed
        except ValueError:
            return str(value)
    if isinstance(model_field, models.IntegerField):
        return int(value)
    return str(value)


def compute_hash(spec: ChainSpec, row: Any) -> str:
    """SHA-256 of the row's content, its position and the previous row's hash."""
    body = {
        "chain": spec.name,
        "sequence": row.sequence,
        "previous_hash": row.previous_hash,
    }
    for name in spec.fields + tuple(ref for _key, ref in spec.refs):
        body[name] = _canonical(row._meta.get_field(name), getattr(row, name))
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def seal(spec: ChainSpec, row: Any, sequence: int, previous_hash: str) -> None:
    """Fill in the chain columns of a row that is about to be written."""
    for key, ref in spec.refs:
        target = getattr(row, f"{key}_id")
        setattr(row, ref, None if target is None else int(target))
    row.sequence = sequence
    row.previous_hash = previous_hash
    row.hash = compute_hash(spec, row)


def row_problems(spec: ChainSpec, row: Any) -> List[str]:
    """What is wrong with a sealed row on its own, ignoring its neighbours."""
    problems = []
    try:
        matches = compute_hash(spec, row) == row.hash
    except (TypeError, ValueError):
        matches = False
    if not matches:
        problems.append("content does not match its hash")
    for key, ref in spec.refs:
        target = getattr(row, f"{key}_id")
        if target is not None and target != getattr(row, ref):
            problems.append(f"{key} was changed")
    return problems


# ── Signatures ────────────────────────────────────────────────────────────────


def _signing_keys() -> List[str]:
    current = getattr(settings, "AUDIT_CHAIN_KEY", "") or settings.SECRET_KEY
    return [current, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]


def _sign(parts: Iterable[Any], key: str) -> str:
    message = json.dumps(list(parts))
    return salted_hmac(_KEY_SALT, message, secret=key, algorithm="sha256").hexdigest()


def sign(*parts: Any) -> str:
    return _sign(parts, _signing_keys()[0])


def signature_matches(signature: str, *parts: Any) -> bool:
    return any(
        constant_time_compare(signature, _sign(parts, key)) for key in _signing_keys()
    )


def head_parts(chain: str, sequence: int, head_hash: str) -> Tuple[Any, ...]:
    return ("head", chain, sequence, head_hash)


def anchor_parts(anchor: Any) -> Tuple[Any, ...]:
    return (
        "anchor",
        anchor.chain,
        anchor.first_sequence,
        anchor.last_sequence,
        anchor.previous_hash,
        anchor.last_hash,
    )


def _atomic(using: str) -> Any:
    # Without Django stubs, type checkers mistake atomic(using) for a decorator.
    return transaction.atomic(using=using)


# ── Writing ───────────────────────────────────────────────────────────────────


def _head_model() -> Any:
    return apps.get_model("audit", "AuditChainHead")


def _anchor_model() -> Any:
    return apps.get_model("audit", "AuditChainAnchor")


def _create_head(spec: ChainSpec, model: Any, using: str) -> None:
    """
    Make the head row when there is none. It is only signed for a chain with no
    history. With history, a missing head means somebody removed it, so the new
    one picks up from the last record but stays unsigned and verification fails.
    """
    last_row = (
        model._base_manager.using(using)
        .filter(sequence__isnull=False)
        .order_by("-sequence")
        .values_list("sequence", "hash")
        .first()
    )
    last_anchor = (
        _anchor_model()
        .objects.using(using)
        .filter(chain=spec.name)
        .order_by("-last_sequence")
        .values_list("last_sequence", "last_hash")
        .first()
    )
    history = [item for item in (last_row, last_anchor) if item]
    if history:
        sequence, head_hash = max(history)
        signature = ""
    else:
        sequence, head_hash = 0, GENESIS_HASH
        signature = sign(*head_parts(spec.name, sequence, head_hash))
    _head_model().objects.using(using).get_or_create(
        chain=spec.name,
        defaults={
            "last_sequence": sequence,
            "head_hash": head_hash or "",
            "signature": signature,
        },
    )


def append(
    spec: ChainSpec,
    model: Any,
    rows: List[Any],
    using: str,
    insert: Callable[[], Any],
) -> Any:
    """Seal ``rows`` onto the end of the chain and run ``insert`` to store them."""
    count = len(rows)
    with _atomic(using):
        heads = _head_model().objects.using(using).filter(chain=spec.name)
        # The UPDATE comes before any read. It locks the row (on SQLite, the
        # database) until commit, so a second writer waits here.
        if not heads.update(last_sequence=F("last_sequence") + count):
            _create_head(spec, model, using)
            heads.update(last_sequence=F("last_sequence") + count)
        head = heads.get()
        sequence = head.last_sequence - count
        intact = signature_matches(
            head.signature, *head_parts(spec.name, sequence, head.head_hash)
        )

        previous = head.head_hash
        for row in rows:
            sequence += 1
            seal(spec, row, sequence, previous)
            previous = row.hash
        result = insert()

        signature = ""
        if intact:
            signature = sign(*head_parts(spec.name, sequence, previous))
        else:
            # Signing it again would hide whatever happened to it. Events are
            # still recorded, and verification keeps failing until someone looks.
            logger.error(
                "Audit chain %r has a bad head signature. Run verify_audit_chain.",
                spec.name,
            )
        heads.update(head_hash=previous, signature=signature)
    return result


class ChainedQuerySet(models.QuerySet):
    def bulk_create(self, objs, batch_size=None, **options):  # type: ignore[override]
        if options.get("ignore_conflicts") or options.get("update_conflicts"):
            raise ValueError(
                "Chained audit rows cannot be bulk created with conflict handling."
            )
        rows = list(objs)
        if not rows:
            return super().bulk_create(rows, batch_size=batch_size, **options)
        model: Any = self.model
        using = self._db or router.db_for_write(model)
        target = self.using(using)

        def insert():
            return super(ChainedQuerySet, target).bulk_create(
                rows, batch_size=batch_size, **options
            )

        return append(model.chain, model, rows, using, insert)

    def update(self, **kwargs):
        """Only detaching a link, e.g. ``update(actor=None)``, is allowed."""
        model: Any = self.model
        detachable = set()
        for key, _ref in model.chain.refs:
            detachable.update((key, f"{key}_id"))
        if any(
            name not in detachable or value is not None
            for name, value in kwargs.items()
        ):
            raise PermissionError(
                f"{model.__name__} records are immutable and cannot be updated."
            )
        return super().update(**kwargs)


class ChainedModel(models.Model):
    """Base class for an append only table whose rows form a hash chain."""

    chain: ChainSpec

    # NULL only for rows written around the model, which verification reports.
    sequence = models.PositiveBigIntegerField(null=True, unique=True, editable=False)
    previous_hash = models.CharField(max_length=64, null=True, editable=False)
    hash = models.CharField(max_length=64, null=True, editable=False)

    objects = cast(Any, ChainedQuerySet).as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError(
                f"{type(self).__name__} records are immutable and cannot be updated."
            )
        model: Any = type(self)
        using = kwargs.get("using") or router.db_for_write(model, instance=self)
        kwargs["using"] = using
        parent = super()
        append(
            self.chain,
            model._meta.concrete_model,
            [self],
            using,
            lambda: parent.save(*args, **kwargs),
        )

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise PermissionError(
            f"{type(self).__name__} records are immutable and cannot be deleted."
        )


def seal_existing_rows(
    spec: ChainSpec, model: Any, head_model: Any, using: str
) -> None:
    """
    Chain the rows that were written before the chain existed, oldest first. Used
    by the migrations, so it takes the (historical) models as arguments.
    """
    table = model._base_manager.using(using)
    ids = list(table.order_by("created_at", "pk").values_list("pk", flat=True))
    columns = ["sequence", "previous_hash", "hash", *(ref for _key, ref in spec.refs)]
    sequence, previous = 0, GENESIS_HASH
    for start in range(0, len(ids), _BACKFILL_BATCH_SIZE):
        batch = ids[start : start + _BACKFILL_BATCH_SIZE]
        found = table.in_bulk(batch)
        rows = [found[pk] for pk in batch]
        for row in rows:
            sequence += 1
            seal(spec, row, sequence, previous)
            previous = row.hash
        table.bulk_update(rows, columns)
    head_model._base_manager.using(using).update_or_create(
        chain=spec.name,
        defaults={
            "last_sequence": sequence,
            "head_hash": previous,
            "signature": sign(*head_parts(spec.name, sequence, previous)),
        },
    )


# ── Retention ─────────────────────────────────────────────────────────────────


def anchor_pruned_rows(
    spec: ChainSpec,
    links: List[Tuple[int, str, str]],
    using: str,
    archive_file: str = "",
) -> List[Any]:
    """
    Record signed anchors for rows that are about to be removed, so the chain can
    still be followed across the hole. ``links`` holds ``(sequence,
    previous_hash, hash)`` for each row. Rows that follow on from each other share
    one anchor. Call it in the same transaction as the delete.
    """
    ranges: List[List[Any]] = []
    for sequence, previous_hash, row_hash in sorted(links):
        last = ranges[-1] if ranges else None
        if last and sequence == last[1] + 1 and previous_hash == last[3]:
            last[1], last[3] = sequence, row_hash
        else:
            ranges.append([sequence, sequence, previous_hash, row_hash])

    anchors = []
    for first, last_sequence, previous_hash, last_hash in ranges:
        anchor = _anchor_model()(
            chain=spec.name,
            first_sequence=first,
            last_sequence=last_sequence,
            previous_hash=previous_hash,
            last_hash=last_hash,
            archive_file=archive_file,
        )
        anchor.signature = sign(*anchor_parts(anchor))
        anchor.save(using=using, force_insert=True)
        anchors.append(anchor)
    return anchors


# ── Verification ──────────────────────────────────────────────────────────────


@dataclass
class ChainReport:
    chain: str
    rows: int = 0
    anchors: int = 0
    head_sequence: int = 0
    head_hash: str = GENESIS_HASH
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class _Segment:
    """One row, or one pruned range, as a link in the walk."""

    first: int
    last: int
    previous_hash: str
    last_hash: str
    problems: List[str]
    label: str


def _row_segments(spec: ChainSpec, rows: Any, report: ChainReport) -> Iterator:
    for row in rows.order_by("sequence").iterator(chunk_size=_CHUNK_SIZE):
        report.rows += 1
        yield _Segment(
            row.sequence,
            row.sequence,
            row.previous_hash,
            row.hash,
            row_problems(spec, row),
            f"record {row.sequence} (id {row.pk})",
        )


def _anchor_segment(anchor: Any) -> _Segment:
    problems = []
    if not signature_matches(anchor.signature, *anchor_parts(anchor)):
        problems.append("signature does not match")
    return _Segment(
        anchor.first_sequence,
        anchor.last_sequence,
        anchor.previous_hash,
        anchor.last_hash,
        problems,
        f"pruned range {anchor.first_sequence}-{anchor.last_sequence}",
    )


def _missing(first: int, last: int) -> str:
    if first == last:
        return f"record {first} is missing"
    return f"records {first}-{last} are missing"


def _walk_chain(
    spec: ChainSpec, model: Any, using: str, expected: List[Tuple[int, str]]
) -> ChainReport:
    report = ChainReport(chain=spec.name)
    errors = report.errors
    table = model._base_manager.using(using)
    heads = _head_model().objects.using(using).filter(chain=spec.name)

    unsealed = table.filter(Q(sequence__isnull=True) | Q(hash__isnull=True))
    for pk in unsealed.order_by("pk").values_list("pk", flat=True):
        errors.append(f"row id {pk} is not chained (written around the application)")

    # Rows added while this runs sit past this point and are left for next time.
    head = heads.first()
    rows = table.filter(sequence__isnull=False, hash__isnull=False)
    if head:
        rows = rows.filter(sequence__lte=head.last_sequence)
    anchors = [
        _anchor_segment(anchor)
        for anchor in _anchor_model()
        .objects.using(using)
        .filter(chain=spec.name)
        .order_by("first_sequence")
    ]
    report.anchors = len(anchors)

    wanted = dict(expected)
    found = {}
    next_sequence, previous = 1, GENESIS_HASH
    for segment in heapq.merge(
        anchors, _row_segments(spec, rows, report), key=lambda item: item.first
    ):
        errors.extend(f"{segment.label}: {problem}" for problem in segment.problems)
        if segment.first > next_sequence:
            errors.append(_missing(next_sequence, segment.first - 1))
        elif segment.first < next_sequence:
            errors.append(f"{segment.label}: this position is already taken")
        elif segment.previous_hash != previous:
            errors.append(f"{segment.label}: does not link to the record before it")
        if segment.last in wanted:
            found[segment.last] = segment.last_hash
        if segment.last >= next_sequence:
            next_sequence, previous = segment.last + 1, segment.last_hash

    # Read the newest row before the head: a writer commits both together.
    newest = table.aggregate(newest=Max("sequence"))["newest"] or 0
    current = heads.first()
    end = next_sequence - 1
    if head is None:
        if current is None and (report.rows or report.anchors):
            errors.append("the chain head is missing")
        report.head_sequence, report.head_hash = end, previous
    else:
        report.head_sequence = head.last_sequence
        report.head_hash = head.head_hash
        if not signature_matches(
            head.signature,
            *head_parts(spec.name, head.last_sequence, head.head_hash),
        ):
            errors.append(
                "the chain head signature does not match: the head was changed "
                "outside the application, or the signing key changed"
            )
        if end < head.last_sequence:
            errors.append(_missing(end + 1, head.last_sequence))
        elif end == head.last_sequence and previous != head.head_hash:
            errors.append("the last record does not match the chain head")
    if current and newest > current.last_sequence:
        errors.append(f"there are records after the chain head, up to {newest}")

    for sequence, row_hash in expected:
        if sequence == 0 and row_hash == GENESIS_HASH:
            continue
        if sequence not in found:
            errors.append(
                f"checkpoint {sequence} cannot be confirmed: the chain no longer "
                "reaches it, or retention pruned it inside a larger range"
            )
        elif found[sequence] != row_hash:
            errors.append(
                f"checkpoint {sequence} does not match: history was rewritten"
            )
    return report


def verify_chain(
    model: Any,
    using: Optional[str] = None,
    expected: Optional[List[Tuple[int, str]]] = None,
) -> ChainReport:
    """
    Walk one chain from the start and report everything that does not add up.
    ``expected`` holds ``(sequence, hash)`` checkpoints saved earlier somewhere
    outside this database.
    """
    spec = model.chain
    alias: str = using or str(router.db_for_write(model))
    anchor_ids = (
        _anchor_model()
        .objects.using(alias)
        .filter(chain=spec.name)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    # A retention run in the middle of a walk moves rows into anchors, so a walk
    # that fails while the anchors changed is done again.
    for _attempt in range(2):
        before = list(anchor_ids.all())
        report = _walk_chain(spec, model, alias, expected or [])
        if report.ok or list(anchor_ids.all()) == before:
            return report
    return _walk_chain(spec, model, alias, expected or [])
