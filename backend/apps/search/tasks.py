import logging

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchVector

from .durable import drop_document, push_document
from .meili_client import get_meili_index
from .models import SearchDocument
from .utils import bump_search_cache_version, sanitize_index_text

logger = logging.getLogger(__name__)


def index_model_for_search(
    app_label,
    model_name,
    object_id,
    title,
    body_text,
    description="",
    tags="",
):
    """
    Background task to update the centralized search index asynchronously.

    Weighted tsvector:
      - title:       Weight 'A' (highest relevance)
      - description: Weight 'B'
      - tags:        Weight 'B'
      - body_text:   Weight 'C' (context/detail)
    """
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
    except ContentType.DoesNotExist:
        return

    sanitized_title = sanitize_index_text(title) or title
    sanitized_description = sanitize_index_text(description)
    sanitized_tags = sanitize_index_text(tags)
    sanitized_body = sanitize_index_text(body_text)

    # Update or create the search document
    doc, created = SearchDocument.objects.update_or_create(
        content_type=content_type,
        object_id=object_id,
        defaults={
            "title": sanitized_title,
            "description": sanitized_description,
            "tags": sanitized_tags,
            "body_text": sanitized_body,
            # Denormalize the content type name for fast API-level filtering
            "content_type_name": model_name,
        },
    )

    # Compute the weighted tsvector in a single UPDATE so Postgres handles
    # language tokenization natively (avoids loading field data into Python).
    from django.db import connection

    if connection.vendor != "sqlite":
        SearchDocument.objects.filter(id=doc.id).update(
            search_vector=(
                SearchVector("title", weight="A")
                + SearchVector("description", weight="B")
                + SearchVector("tags", weight="B")
                + SearchVector("body_text", weight="C")
            )
        )

    # Sync to Meilisearch (bounded retries, dead-letter row on failure)
    push_document(doc)

    bump_search_cache_version()


def remove_model_from_search(app_label, model_name, object_id):
    """
    Background task to remove a deleted object from the search index.
    """
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        docs = SearchDocument.objects.filter(
            content_type=content_type, object_id=object_id
        )

        for doc in docs:
            # Delete from Meilisearch first; a failure leaves a dead-letter row
            # because the DB row below is removed either way.
            drop_document(doc.id, content_type, object_id)

        docs.delete()
        bump_search_cache_version()
    except ContentType.DoesNotExist:
        pass


def reconcile_search_index():
    from django.apps import apps
    from django_q.tasks import async_task

    from apps.search.meili_client import get_meili_index
    from apps.search.mixins import SearchIndexMixin
    from apps.search.models import SearchDocument

    index = get_meili_index()
    if not index:
        return

    # 1. Query Meilisearch for all doc IDs
    ms_ids = set()
    limit = 1000
    offset = 0
    while True:
        res = index.get_documents({"limit": limit, "offset": offset, "fields": ["id"]})
        docs = res.results if hasattr(res, "results") else res
        if not docs:
            break
        ms_ids.update(str(d["id"]) for d in docs)
        offset += limit

    # 2. Query DB for all active IDs from SearchDocument
    all_db_docs = list(SearchDocument.objects.values_list("id", flat=True))
    db_ids = set(str(pk) for pk in all_db_docs)

    missing_in_ms = db_ids - ms_ids
    stale_in_ms = ms_ids - db_ids

    # 3. Re-index missing (These are in SearchDocument but missing in Meili)
    for doc_id in missing_in_ms:
        try:
            doc = SearchDocument.objects.get(id=int(doc_id))
            # Just push the existing document to Meilisearch
            index.add_documents(
                [
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "description": doc.description,
                        "tags": doc.tags,
                        "body_text": doc.body_text,
                        "content_type_name": doc.content_type_name,
                    }
                ]
            )
        except SearchDocument.DoesNotExist:
            pass

    # 4. Remove stale (These are in Meili but not in SearchDocument)
    for doc_id in stale_in_ms:
        index.delete_document(doc_id)
