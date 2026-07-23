from django.core.management.base import BaseCommand
from django.db import transaction
from apps.issues.models import Bounty
from apps.progress.models import Badge


class Command(BaseCommand):
    help = "Seeds the database with educational open-source bounties"

    def handle(self, *args, **options):
        self.stdout.write("Seeding educational bounties...")

        # 1. Ensure Badge exists
        badge, _ = Badge.objects.get_or_create(
            slug="bounty-hunter",
            defaults={
                "name": "Bounty Hunter",
                "description": "Completed open-source practice bounties.",
                "category": "bounties",
            },
        )

        # 2. Define Bounties data
        bounties_data = [
            {
                "title": "Conventional Commits Compliance",
                "description": "Open-source projects enforce strict standards for commit messages to ensure clean changelogs. In this bounty, your goal is to correct a contributor's commit history to conform to Conventional Commits guidelines (e.g., using prefixes like 'feat:', 'fix:', 'docs:', 'chore:'). Learn how conventional formatting helps maintainers parse history automatically.",
                "xp_reward": 100,
                "badge": badge,
            },
            {
                "title": "Git Rebase & Commit Squashing",
                "description": "A contributor opened a PR, but it has 8 small, messy commits like 'fixed bug', 'typo', 'testing again'. A maintainer asked them to squash these into a single clean commit. Refactor the branch commit history using git rebase -i to squash all commits into a single clean commit titled 'feat: implement token caching on client'.",
                "xp_reward": 150,
                "badge": badge,
            },
            {
                "title": "Resolve Git Merge Conflict in Index Page",
                "description": "Upstream changes on the 'main' branch have introduced a merge conflict on 'index.html'. Merge the latest 'main' branch into your feature branch, resolve the conflict markings (<<<<<<<, =======, >>>>>>>), verify that the HTML layout remains clean, and commit your resolved code.",
                "xp_reward": 200,
                "badge": badge,
            },
            {
                "title": "Parameterize Raw SQL Query (SQL Injection)",
                "description": "Security checks flagged a vulnerability where user-supplied search queries are directly interpolated into a raw SQL query string. Refactor the database query to use query parameterization (or Django ORM filters) to prevent SQL Injection attacks and secure the input fields.",
                "xp_reward": 250,
                "badge": badge,
            },
            {
                "title": "Write Unit Tests for Date Utilities",
                "description": "Good open-source contributions always include test coverage. The utility module lacks tests for timezone conversion helper functions. Write unit tests using pytest that test standard timezone offsets, daylight savings transitions, and invalid inputs to ensure no future regressions.",
                "xp_reward": 120,
                "badge": badge,
            },
        ]

        # 3. Create or update Bounties
        with transaction.atomic():
            for data in bounties_data:
                bounty, created = Bounty.objects.get_or_create(
                    title=data["title"],
                    defaults={
                        "description": data["description"],
                        "xp_reward": data["xp_reward"],
                        "status": Bounty.Status.OPEN,
                        "badge": data["badge"],
                    },
                )
                if not created:
                    bounty.description = data["description"]
                    bounty.xp_reward = data["xp_reward"]
                    bounty.status = Bounty.Status.OPEN
                    bounty.badge = data["badge"]
                    bounty.save()

        self.stdout.write(
            self.style.SUCCESS("Successfully seeded educational bounties!")
        )
