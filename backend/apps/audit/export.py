"""Streaming CSV and JSON export for the audit log.

The export view used to serialize every matching event into one list and then
build the whole file in memory. Here the queryset is read with ``iterator()``
and each row is written out as soon as it is built, so memory stays flat no
matter how many events match.
"""

import csv
import json
from datetime import date

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse, StreamingHttpResponse

from apps.audit.serializers import AuditEventSerializer

EXPORT_FORMATS = ("csv", "json")

# How many rows the database cursor fetches at a time.
EXPORT_CHUNK_SIZE = 500

CSV_HEADER = [
    "ID",
    "Timestamp",
    "Actor",
    "Action",
    "Model Type",
    "Resource ID",
    "Summary",
    "Correlation ID",
    "IP Address",
]

# Spreadsheets run a cell as a formula when it starts with one of these.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class _Echo:
    """File-like object whose write() just hands the value back, so
    csv.writer can be used to produce chunks for a streaming response."""

    def write(self, value):
        return value


def _safe_cell(value):
    """Stop attacker controlled text (user agent, resource type, ...) from
    turning into a spreadsheet formula."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _csv_row(item):
    return [
        _safe_cell(cell)
        for cell in (
            item.get("id"),
            item.get("created_at"),
            item.get("actor_username") or "System",
            item.get("action"),
            item.get("resource_type"),
            item.get("resource_id"),
            item.get("summary"),
            item.get("correlation_id"),
            item.get("ip_address"),
        )
    ]


def _rows(queryset):
    serializer = AuditEventSerializer()
    for event in queryset.iterator(chunk_size=EXPORT_CHUNK_SIZE):
        yield serializer.to_representation(event)


def stream_csv(queryset):
    writer = csv.writer(_Echo())
    yield writer.writerow(CSV_HEADER)
    for item in _rows(queryset):
        yield writer.writerow(_csv_row(item))


def stream_json(queryset):
    """Yield a JSON array one element per chunk. An empty result is ``[]``."""
    yield "["
    first = True
    for item in _rows(queryset):
        yield ("\n" if first else ",\n") + json.dumps(item, cls=DjangoJSONEncoder)
        first = False
    yield "\n]\n" if not first else "]\n"


def export_response(queryset, export_format, today=None):
    """Build the download response for ``csv`` or ``json``.

    An unknown format is a 400 rather than silently returning the paged list.
    """
    export_format = (export_format or "").lower()
    if export_format not in EXPORT_FORMATS:
        return JsonResponse(
            {
                "detail": "Unsupported export format. Use one of: "
                + ", ".join(EXPORT_FORMATS)
                + "."
            },
            status=400,
        )

    if export_format == "csv":
        stream, content_type = stream_csv(queryset), "text/csv"
    else:
        stream, content_type = stream_json(queryset), "application/json"

    response = StreamingHttpResponse(stream, content_type=content_type)
    stamp = (today or date.today()).isoformat()
    response["Content-Disposition"] = (
        f'attachment; filename="audit_logs_{stamp}.{export_format}"'
    )
    # Do not let a proxy hold the whole body back before sending it on.
    response["X-Accel-Buffering"] = "no"
    return response
