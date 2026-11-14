"""Read-only checks for the records installed by the local seed commands."""

from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.content.management.commands.seed_lessons import CURRICULUM_LESSONS
from apps.content.models import Exercise, Lesson
from apps.dashboard.models import Issue, PullRequest
from apps.progress.models import Certificate, LessonProgress

DASHBOARD_LESSONS = (
    ("intro-os", "Introduction to open-source"),
    ("git-branches", "Mastering local Git branches"),
    ("make-prs", "Making pull requests with ease"),
    ("git-conflicts", "Resolving scary conflicts"),
    ("git-rebase", "Clean commits & Rebase flows"),
)
DEMO_USERS = ("admin", "alice", "bob", "charlie", "diana")


class Command(BaseCommand):
    help = "Verify local curriculum/dashboard seed invariants without changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope", choices=("all", "curriculum", "dashboard"), default="all"
        )

    def handle(self, *args, **options):
        errors = []

        def require_one(label, count):
            if count != 1:
                errors.append(f"{label}: expected 1, found {count}")

        def check_lesson(slug, exercise_titles):
            rows = list(
                Lesson.objects.filter(slug=slug).values("id", "organization_id")
            )
            require_one(f"lesson {slug}", len(rows))
            if len(rows) != 1:
                return
            if rows[0]["organization_id"] is not None:
                errors.append(f"lesson {slug}: seed lesson must be global")
            counts = Counter(
                Exercise.objects.filter(lesson_id=rows[0]["id"]).values_list(
                    "title", flat=True
                )
            )
            for title in exercise_titles:
                require_one(f"exercise {slug}/{title}", counts[title])

        if options["scope"] in ("all", "curriculum"):
            for entry in CURRICULUM_LESSONS:
                check_lesson(
                    entry["slug"],
                    [exercise["title"] for exercise in entry["exercises"]],
                )

        if options["scope"] in ("all", "dashboard"):
            User = get_user_model()
            for username in DEMO_USERS:
                require_one(
                    f"dashboard user {username}",
                    User.objects.filter(username=username).count(),
                )
            for slug, title in DASHBOARD_LESSONS:
                check_lesson(slug, [f"Exercise: {title}"])
            for username, slugs in (
                ("alice", DASHBOARD_LESSONS[:4]),
                ("bob", DASHBOARD_LESSONS[:3]),
                ("charlie", DASHBOARD_LESSONS[:2]),
            ):
                for slug, _ in slugs:
                    require_one(
                        f"completed progress {username}/{slug}",
                        LessonProgress.objects.filter(
                            user__username=username, lesson__slug=slug, completed=True
                        ).count(),
                    )
            require_one(
                "active demo certificate alice/test-cert-hash-12345",
                Certificate.objects.filter(
                    user__username="alice",
                    verification_hash="test-cert-hash-12345",
                    is_active=True,
                ).count(),
            )
            # Representative relationships used by dashboard charts, not total counts:
            # contributors may create additional issues/PRs after seeding.
            require_one(
                "dashboard issue Fix dark mode contrast in forms",
                Issue.objects.filter(
                    title="Fix dark mode contrast in forms",
                    assigned_to__username="alice",
                    status=Issue.Status.SOLVED,
                ).count(),
            )
            require_one(
                "merged demo PR feat: solve dark mode contrast issues",
                PullRequest.objects.filter(
                    title="feat: solve dark mode contrast issues",
                    user__username="alice",
                    status=PullRequest.Status.MERGED,
                    issue__title="Fix dark mode contrast in forms",
                    merged_at__isnull=False,
                ).count(),
            )

        if errors:
            for error in errors:
                self.stderr.write(f"FAIL: {error}")
            raise CommandError(
                f"Seed verification failed ({len(errors)} invariants). "
                "Review the diagnostics; seed_lessons / seed_dashboard can populate "
                "a disposable local database. No records were changed."
            )
        self.stdout.write(f"Seed verification passed ({options['scope']}); read-only.")
