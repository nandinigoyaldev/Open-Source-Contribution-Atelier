from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchVector

from .models import SearchDocument
from .utils import bump_search_cache_version


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
    SearchDocument.objects.filter(id=doc.id).update(
        search_vector=(
            SearchVector("title", weight="A")
            + SearchVector("description", weight="B")
            + SearchVector("tags", weight="B")
            + SearchVector("body_text", weight="C")
        )
    )

    bump_search_cache_version()


def remove_model_from_search(app_label, model_name, object_id):
    """
    Background task to remove a deleted object from the search index.
    """
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        SearchDocument.objects.filter(
            content_type=content_type, object_id=object_id
        ).delete()
        bump_search_cache_version()
    except ContentType.DoesNotExist:
        pass
