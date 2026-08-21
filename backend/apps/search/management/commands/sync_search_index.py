from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Syncs search index content into Meilisearch."

    def handle(self, *args, **options):
        documents = self.get_documents_to_sync()
        success_count = 0
        error_count = 0

        for doc in documents:
            try:
                # Process and extract searchable text
                searchable_text = extract_searchable_text(doc.content)
                self.index_document(doc, searchable_text)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(
                    f"Skipping malformed document ID {doc.id} due to parsing error: {e}"
                )
                # Continue processing remaining records
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete. Successfully synced: {success_count}, Warnings/Errors logged: {error_count}"
            )
        )
