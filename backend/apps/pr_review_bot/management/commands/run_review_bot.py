"""
Management command to run PR review bot.
"""

from django.core.management.base import BaseCommand
from apps.pr_review_bot.tasks import review_pr


class Command(BaseCommand):
    """
    Run PR review bot.

    Usage:
        python manage.py run_review_bot --repo owner/repo --pr 123
    """

    help = "Run PR review bot"

    def add_arguments(self, parser):
        parser.add_argument(
            "--repo", type=str, required=True, help="Repository (owner/repo)"
        )
        parser.add_argument("--pr", type=int, required=True, help="PR number")

    def handle(self, *args, **options):
        repo = options["repo"]
        pr_number = options["pr"]

        self.stdout.write(f"🚀 Starting PR review for #{pr_number} in {repo}")

        result = review_pr(repo, pr_number)

        self.stdout.write(f"✅ Review completed: {result}")
