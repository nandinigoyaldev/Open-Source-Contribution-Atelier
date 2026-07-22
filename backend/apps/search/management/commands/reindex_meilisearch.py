from django.core.management.base import BaseCommand
from apps.search.models import SearchDocument
from apps.search.meili_client import setup_meilisearch_index


class Command(BaseCommand):
    help = "Re-indexes all SearchDocument records from the database into Meilisearch."

    def handle(self, *args, **options):
        self.stdout.write("Initializing Meilisearch index and settings...")
        index = setup_meilisearch_index()
        if not index:
            self.stderr.write(
                "Meilisearch is not available or configured. Cannot re-index."
            )
            return

        documents = SearchDocument.objects.all().select_related("content_type")
        total_docs = documents.count()
        self.stdout.write(
            f"Found {total_docs} search documents in the database to index."
        )

        if total_docs == 0:
            self.stdout.write(self.style.SUCCESS("No documents to index. Done."))
            return

        # Prepare documents in batches of 100
        batch_size = 100
        batch = []
        indexed_count = 0

        for doc in documents:
            batch.append(
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "description": doc.description,
                    "tags": doc.tags,
                    "body_text": doc.body_text,
                    "content_type_name": doc.content_type_name,
                }
            )

            if len(batch) >= batch_size:
                try:
                    index.add_documents(batch)
                    indexed_count += len(batch)
                    self.stdout.write(
                        f"Indexed {indexed_count}/{total_docs} documents..."
                    )
                except Exception as exc:
                    self.stderr.write(f"Failed to index batch: {exc}")
                batch = []

        # Index remaining documents
        if batch:
            try:
                index.add_documents(batch)
                indexed_count += len(batch)
                self.stdout.write(f"Indexed {indexed_count}/{total_docs} documents...")
            except Exception as exc:
                self.stderr.write(f"Failed to index final batch: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully re-indexed {indexed_count} documents to Meilisearch."
            )
        )
