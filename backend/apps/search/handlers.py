import logging
import sys

from django_q.tasks import async_task
from apps.events.registry import event_handler

logger = logging.getLogger(__name__)

def _safe_async(task_path, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    try:
        async_task(task_path, **kwargs)
    except Exception as exc:
        logger.warning(
            "Django-Q broker unavailable; skipping search indexing task: %s", exc
        )

@event_handler("SearchIndexRequested")
def handle_search_index_requested(event_data: dict):
    """
    Handles indexing requests from any domain via the EventBus.
    Search app no longer needs to import models from other apps.
    
    Expected event_data format:
    {
        "app_label": str,
        "model_name": str,
        "object_id": int,
        "title": str,
        "description": str,
        "tags": str,
        "body_text": str
    }
    """
    _safe_async(
        "apps.search.tasks.index_model_for_search",
        **event_data
    )

@event_handler("SearchDeindexRequested")
def handle_search_deindex_requested(event_data: dict):
    """
    Handles de-indexing requests from any domain.
    
    Expected event_data format:
    {
        "app_label": str,
        "model_name": str,
        "object_id": int
    }
    """
    _safe_async(
        "apps.search.tasks.remove_model_from_search",
        **event_data
    )
