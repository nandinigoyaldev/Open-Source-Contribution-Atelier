from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchVector

from .models import SearchDocument


@shared_task
def index_model_for_search(app_label, model_name, object_id, title, body_text):
    """
    Background task to update the centralized search index asynchronously.
    """
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
    except ContentType.DoesNotExist:
        return

    # Update or create the search document
    doc, created = SearchDocument.objects.update_or_create(
        content_type=content_type,
        object_id=object_id,
        defaults={"title": title, "body_text": body_text},
    )

    # Compute the tsvector. We do this by updating it based on the fields.
    # Postgres handles the language tokenization natively.
    SearchDocument.objects.filter(id=doc.id).update(
        search_vector=SearchVector("title", weight="A")
        + SearchVector("body_text", weight="B")
    )


@shared_task
def remove_model_from_search(app_label, model_name, object_id):
    """
    Background task to remove a deleted object from the search index.
    """
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        SearchDocument.objects.filter(
            content_type=content_type, object_id=object_id
        ).delete()
    except ContentType.DoesNotExist:
        pass
