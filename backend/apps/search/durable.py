"""
Durable Meilisearch writes: bounded retries plus a dead-letter record.

Tasks run inside django-q workers, so the in-task backoff is deliberately short
(about two seconds in total). Anything that still fails is stored in
``SearchIndexFailure`` and can be replayed with ``replay_search_failures``.
"""

import logging
import time

from django.utils import timezone

from .meili_client import MeiliSearchConnectionError, get_meili_index
from .models import SearchDocument, SearchIndexFailure

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAYS = (0.5, 1.5)  # seconds slept before attempt 2 and 3
ERROR_MAX_LENGTH = 500

_TRANSIENT_STATUS_CODES = {408, 429}


def build_payload(doc):
    return {
        "id": str(doc.id),
        "title": doc.title,
        "description": doc.description,
        "tags": doc.tags,
        "body_text": doc.body_text,
        "content_type_name": doc.content_type_name,
    }


def is_transient(exc):
    """Connection problems, timeouts and 5xx/408/429 are retried; other 4xx are not."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status >= 500 or status in _TRANSIENT_STATUS_CODES
    if isinstance(exc, (OSError, TimeoutError)):
        return True
    return MeiliSearchConnectionError is not Exception and isinstance(
        exc, MeiliSearchConnectionError
    )


def is_missing_document(exc):
    return (
        getattr(exc, "status_code", None) == 404
        or getattr(exc, "code", None) == "document_not_found"
    )


def call_with_retries(func, attempts=MAX_ATTEMPTS, delays=RETRY_DELAYS):
    """
    Run ``func`` and return ``(error, attempts_used)``; ``error`` is None on
    success. Permanent errors are returned straight away without retrying.
    """
    used = 0
    while True:
        used += 1
        try:
            func()
            return None, used
        except Exception as exc:  # the client raises several unrelated types
            if not is_transient(exc) or used >= attempts:
                return exc, used
            time.sleep(delays[min(used - 1, len(delays) - 1)])


def _truncate(exc):
    return f"{type(exc).__name__}: {exc}"[:ERROR_MAX_LENGTH]


def record_failure(*, document_id, content_type, object_id, operation, error, attempts):
    """Create or update the single open failure row for this document+operation."""
    now = timezone.now()
    row, created = SearchIndexFailure.objects.get_or_create(
        document_id=str(document_id),
        operation=operation,
        defaults={
            "content_type": content_type,
            "object_id": object_id,
            "attempts": attempts,
            "last_error": _truncate(error),
            "first_failed_at": now,
            "last_failed_at": now,
        },
    )
    if not created:
        row.content_type = content_type
        row.object_id = object_id
        row.attempts += attempts
        row.last_error = _truncate(error)
        row.last_failed_at = now
        row.save()
    logger.error(
        "Meilisearch %s of document %s failed after %s attempt(s): %s",
        operation,
        document_id,
        attempts,
        error,
    )
    return row


def clear_failure(document_id, operation):
    SearchIndexFailure.objects.filter(
        document_id=str(document_id), operation=operation
    ).delete()


def push_document(doc, index=None):
    """Index one SearchDocument with retries. Returns True on success."""
    index = index if index is not None else get_meili_index()
    if not index:
        return True  # Meilisearch not configured: nothing to be durable about
    error, attempts = call_with_retries(
        lambda: index.add_documents([build_payload(doc)])
    )
    if error is None:
        clear_failure(doc.id, SearchIndexFailure.OP_INDEX)
        return True
    record_failure(
        document_id=doc.id,
        content_type=doc.content_type,
        object_id=doc.object_id,
        operation=SearchIndexFailure.OP_INDEX,
        error=error,
        attempts=attempts,
    )
    return False


def drop_document(doc_id, content_type, object_id, index=None):
    """Delete one document from Meilisearch with retries. Missing counts as done."""
    index = index if index is not None else get_meili_index()
    if not index:
        return True
    error, attempts = call_with_retries(lambda: index.delete_document(str(doc_id)))
    if error is not None and is_missing_document(error):
        error = None
    if error is None:
        clear_failure(doc_id, SearchIndexFailure.OP_DELETE)
        return True
    record_failure(
        document_id=doc_id,
        content_type=content_type,
        object_id=object_id,
        operation=SearchIndexFailure.OP_DELETE,
        error=error,
        attempts=attempts,
    )
    return False


def replay_failure(failure, index=None):
    """
    Retry one failure row. The current SearchDocument is read from the database
    (nothing is stored in the failure row), so a replay can never overwrite
    newer data. Returns True when the row was resolved and removed.
    """
    if failure.operation == SearchIndexFailure.OP_DELETE:
        return drop_document(
            failure.document_id, failure.content_type, failure.object_id, index
        )

    doc = SearchDocument.objects.filter(id=failure.document_id).first()
    if doc is None:
        # The object was removed since; the delete path owns Meilisearch cleanup.
        failure.delete()
        return True
    return push_document(doc, index)
