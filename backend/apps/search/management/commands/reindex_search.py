from django.core.management.base import BaseCommand

from apps.content.models import Lesson
from apps.issues.models import IssueReport
from apps.search.tasks import index_model_for_search


class Command(BaseCommand):
    help = "Re-indexes all Lesson and IssueReport records into the SearchDocument database."

    def handle(self, *args, **options):
        self.stdout.write("Reindexing Lessons...")
        lessons = Lesson.objects.all()
        for lesson in lessons:
            index_model_for_search(
                app_label="content",
                model_name="lesson",
                object_id=lesson.id,
                title=lesson.title,
                body_text=lesson.content,
                description=lesson.summary,
            )
        self.stdout.write(self.style.SUCCESS(f"Reindexed {lessons.count()} Lessons."))

        self.stdout.write("Reindexing IssueReports...")
        issues = IssueReport.objects.all()
        for issue in issues:
            index_model_for_search(
                app_label="issues",
                model_name="issuereport",
                object_id=issue.id,
                title=issue.title,
                description=issue.description,
                body_text="",
            )
        self.stdout.write(
            self.style.SUCCESS(f"Reindexed {issues.count()} IssueReports.")
        )
        self.stdout.write(self.style.SUCCESS("Full text search reindexing complete."))
