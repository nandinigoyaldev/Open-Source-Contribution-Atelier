from django.core.management.base import BaseCommand

from apps.content.models import Lesson
from apps.content.semantic_search import encode, is_available


class Command(BaseCommand):
    help = "Pre-compute semantic embeddings for all lessons."

    def handle(self, *args, **options):
        if not is_available():
            self.stdout.write(
                self.style.ERROR(
                    "Semantic search model not available. Install sentence-transformers."
                )
            )
            return

        lessons = Lesson.objects.all()
        if not lessons.exists():
            self.stdout.write(self.style.WARNING("No lessons found."))
            return

        texts = []
        for lesson in lessons:
            text = f"{lesson.title}. {lesson.summary} {lesson.content}"
            texts.append(text)

        self.stdout.write(f"Computing embeddings for {len(texts)} lessons...")
        embeddings = encode(texts)

        if embeddings is None:
            self.stdout.write(self.style.ERROR("Failed to compute embeddings."))
            return

        for lesson, vec in zip(lessons, embeddings):
            lesson.embedding = vec.tolist()
            lesson.save(update_fields=["embedding"])

        self.stdout.write(
            self.style.SUCCESS(f"Embedded {len(lessons)} lessons successfully.")
        )
