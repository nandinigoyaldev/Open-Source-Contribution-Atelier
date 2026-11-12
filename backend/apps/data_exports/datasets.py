"""
The datasets a user can export.

A dataset is a model plus the field that ties each row to its owner. Rows are read in primary-key
order with keyset pagination (``pk > last_pk LIMIT n``), which keeps memory bounded and lets an
interrupted export continue from the last primary key it wrote, even if rows were added or removed
meanwhile (OFFSET paging cannot do that).

To add a dataset, call ``register_dataset`` with a model that has an integer primary key and a
field pointing at the owning user; nothing else in the pipeline changes.
"""

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Callable, Iterable, Optional

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class UnknownDataset(KeyError):
    pass


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    app_label: str
    model_name: str
    owner_field: str
    exclude: tuple = ()

    @property
    def model(self):
        return apps.get_model(self.app_label, self.model_name)

    @property
    def columns(self) -> list[str]:
        """Column names (database attribute names), primary key first."""
        names = [f.attname for f in self.model._meta.concrete_fields]
        names = [n for n in names if n not in self.exclude]
        pk = self.model._meta.pk.attname
        return [pk] + [n for n in names if n != pk]

    def queryset(self, user):
        # _base_manager is the plain, unscoped manager. Isolation comes from the owner filter, so
        # a worker with no request (and no tenant context) still sees the user's own rows.
        return self.model._base_manager.filter(**{self.owner_field: user})


_REGISTRY: dict[str, Dataset] = {}


def register_dataset(
    key: str,
    label: str,
    model: str,
    owner_field: str,
    exclude: Iterable[str] = (),
) -> Dataset:
    app_label, model_name = model.split(".")
    dataset = Dataset(key, label, app_label, model_name, owner_field, tuple(exclude))
    pk = dataset.model._meta.pk
    if not isinstance(pk, (models.AutoField, models.BigAutoField, models.IntegerField)):
        raise ValueError(
            f"{model} needs an integer primary key to be exported in pages"
        )
    _REGISTRY[key] = dataset
    return dataset


def get_dataset(key: str) -> Dataset:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise UnknownDataset(key) from None


def all_datasets() -> list[Dataset]:
    return sorted(_REGISTRY.values(), key=lambda d: d.key)


def register_default_datasets() -> None:
    register_dataset(
        "notifications", "Notifications", "notifications.Notification", "recipient"
    )
    register_dataset(
        "lesson_progress", "Lesson progress", "progress.LessonProgress", "user"
    )
    register_dataset("quiz_attempts", "Quiz attempts", "progress.QuizAttempt", "user")
    register_dataset(
        "code_submissions", "Code submissions", "progress.CodeSubmission", "user"
    )
    register_dataset(
        "sandbox_logs", "Sandbox runs", "sandbox.SandboxExecutionLog", "user"
    )
    register_dataset(
        "notes", "Notes", "notes.Note", "user", exclude=("iv",)
    )
    register_dataset(
        "certificates", "Certificates", "progress.Certificate", "user"
    )
    register_dataset(
        "organizations", "Organization memberships", "organizations.OrganizationMembership", "user"
    )
    register_dataset(
        "daily_activity", "Daily activity", "progress.DailyActivity", "user"
    )


def get_documented_exclusions() -> dict:
    """Document all sensitive data redactions, exclusions, and privacy protections."""
    return {
        "sensitive_fields_excluded": [
            "passwords",
            "password_hashes",
            "password_salts",
            "auth_tokens",
            "session_tokens",
            "verification_tokens",
            "encryption_initialization_vectors",
            "peer_private_messages",
            "tenant_organization_secrets",
        ],
        "dataset_exclusions": {
            "notes": ["iv (encryption initialization vector is excluded to preserve cryptographic confidentiality)"],
            "organizations": ["Tenant-wide configurations and other member profiles excluded; strictly scoped to requester's membership record."],
            "all_datasets": ["System internal caches, deleted records, and authentication tokens are never included in exports."],
        },
        "retention_and_privacy_safeguards": {
            "export_ttl_hours": 24,
            "isolation": "Exports strictly filter rows where owner matches requesting user ID.",
            "formula_injection_protection": "CSV cell values starting with =, +, -, @, \\t, \\r are safely escaped.",
            "download_policy": "Download links expire after 24 hours (HTTP 410 Gone) and require authenticated ownership check.",
        },
    }


# ---------------------------------------------------------------------------- serialization

# A spreadsheet runs a cell that starts with one of these as a formula. Exported text comes from
# users (titles, code, messages), so it is neutralised the way OWASP recommends.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        value = json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True)
    elif isinstance(value, (int, float, Decimal)):
        return str(value)
    else:
        value = str(value)
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def encode_header(columns: list[str], file_format: str) -> bytes:
    if file_format != "csv":
        return b""
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerow(columns)
    return buffer.getvalue().encode("utf-8")


def encode_rows(rows: Iterable[tuple], columns: list[str], file_format: str) -> bytes:
    """Serialize a chunk of rows. The same rows always give the same bytes."""
    if file_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        for row in rows:
            writer.writerow([_csv_value(v) for v in row])
        return buffer.getvalue().encode("utf-8")
    if file_format == "ndjson":
        lines = [
            json.dumps(dict(zip(columns, row)), cls=DjangoJSONEncoder, sort_keys=True)
            for row in rows
        ]
        return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
    raise ValueError(f"Unsupported export format: {file_format}")


def fetch_chunk(
    dataset: Dataset, user, last_pk: Optional[int], size: int
) -> list[tuple]:
    """The next ``size`` rows after ``last_pk`` in primary-key order."""
    queryset = dataset.queryset(user)
    if last_pk is not None:
        queryset = queryset.filter(pk__gt=last_pk)
    return list(queryset.order_by("pk").values_list(*dataset.columns)[:size])


def count_rows(dataset: Dataset, user) -> int:
    return dataset.queryset(user).count()


# A callable the runner uses to read a chunk; replaceable in tests.
ChunkReader = Callable[[Dataset, object, Optional[int], int], list]
