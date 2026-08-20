import logging
from django.core.management.base import BaseCommand
from apps.search.utils import extract_searchable_text

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Syncs searchable lesson content and forum posts into Meilisearch."

    def handle(self, *args, **options):
        # Example document iteration loop
        documents = [] # Fetch documents from models
        for doc in documents:
            try:
                searchable_text = extract_searchable_text(doc.content)
                # Index document into Meilisearch...
            except Exception as e:
                # Acceptance Criteria: Log warning and continue processing remaining records
                logger.warning(f"Skipping malformed document ID {doc.id} due to parsing error: {e}")
                continue
        self.stdout.write(self.style.SUCCESS("Successfully completed search index bulk sync."))
