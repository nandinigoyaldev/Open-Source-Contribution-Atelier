import logging

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchVector

from .meili_client import get_meili_index
from .models import SearchDocument
from .utils import bump_search_cache_version

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

    # Update or create the search document
    doc, created = SearchDocument.objects.update_or_create(
        content_type=content_type,
        object_id=object_id,
        defaults={
            "title": title,
            "description": description,
            "tags": tags,
            "body_text": body_text,
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

    # Sync to Meilisearch
    try:
        index = get_meili_index()
        if index:
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
    except Exception as exc:
        logger.warning("Failed to index document %s in Meilisearch: %s", doc.id, exc)

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
            # Delete from Meilisearch first
            try:
                index = get_meili_index()
                if index:
                    index.delete_document(str(doc.id))
            except Exception as exc:
                logger.warning(
                    "Failed to delete document %s from Meilisearch: %s", doc.id, exc
                )

        docs.delete()
        bump_search_cache_version()
    except ContentType.DoesNotExist:
        pass
