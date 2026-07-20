from django.core.management.base import BaseCommand

from apps.challenges.models import Challenge
from apps.content.models import Exercise, Lesson
from apps.progress.models import Badge
from apps.issues.models import Bounty


class Command(BaseCommand):
    help = "Seed baseline content for Open Source Contribution Atelier"

    def handle(self, *args, **options):
        # 1. Lessons and Exercises from frontend/src/lib/lessons.ts
        lessons_data = [
            {
                "slug": "intro",
                "title": "Why Git & GitHub?",
                "summary": "Understand the importance of version control and collaboration.",
                "content": "Git lets you track changes, revert mistakes, and work on multiple features safely. GitHub adds a social layer: sharing, reviewing, and contributing to open-source projects.",
                "exercises": [
                    {
                        "title": "Introduction",
                        "prompt": "Press Enter to continue.",
                        "expected_command": ".+",
                        "explanation": "This is a warm-up exercise.",
                        "points": 10,
                    }
                ],
            },
            {
                "slug": "git-init",
                "title": "Initialize a Repository",
                "summary": "Create a new Git repository.",
                "content": "The `git init` command creates a .git folder and starts tracking.",
                "exercises": [
                    {
                        "title": "Initialize Repository",
                        "prompt": "Type the command to initialize a repository.",
                        "expected_command": "git init",
                        "explanation": "The `git init` command creates a .git folder.",
                        "points": 20,
                    }
                ],
            },
            {
                "slug": "git-add",
                "title": "Stage Files",
                "summary": "Add files to the staging area.",
                "content": "`git add <file>` tells Git to include changes in the next commit.",
                "exercises": [
                    {
                        "title": "Stage All Changes",
                        "prompt": "Type the command to stage all currently modified files.",
                        "expected_command": "git add .",
                        "explanation": "The dot refers to the current directory.",
                        "points": 20,
                    }
                ],
            },
            {
                "slug": "git-commit",
                "title": "Create a Commit",
                "summary": "Record your changes.",
                "content": '`git commit -m "msg"` creates a new commit with a message.',
                "exercises": [
                    {
                        "title": "Commit with message",
                        "prompt": "Type a commit command with the message 'Init project'.",
                        "expected_command": 'git commit -m "Init project"',
                        "explanation": "Use -m followed by the message in quotes.",
                        "points": 30,
                    }
                ],
            },
        ]

        for ld in lessons_data:
            lesson, _ = Lesson.objects.get_or_create(
                slug=ld["slug"],
                defaults={
                    "title": ld["title"],
                    "summary": ld["summary"],
                    "content": ld["content"],
                    "difficulty": "beginner",
                },
            )
            for ed in ld["exercises"]:
                Exercise.objects.get_or_create(
                    lesson=lesson,
                    title=ed["title"],
                    defaults={
                        "prompt": ed["prompt"],
                        "expected_command": ed["expected_command"],
                        "explanation": ed["explanation"],
                        "points": ed["points"],
                    },
                )

        # 2. Challenges
        challenges_data = [
            {
                "title": "Hacktoberfest Warmup",
                "slug": "hacktoberfest-warmup",
                "summary": "Guide contributors through issue triage, branch naming, and clean commits.",
                "difficulty": "intermediate",
                "points": 50,
                "is_featured": True,
            },
            {
                "title": "Git Recovery Lab",
                "slug": "git-recovery-lab",
                "summary": "Practice safe undo flows, rebases, and fixing a messy working tree.",
                "difficulty": "advanced",
                "points": 100,
                "is_featured": False,
            },
        ]

        for cd in challenges_data:
            Challenge.objects.get_or_create(
                slug=cd["slug"],
                defaults={
                    "title": cd["title"],
                    "summary": cd["summary"],
                    "difficulty": cd["difficulty"],
                    "points": cd["points"],
                    "is_featured": cd["is_featured"],
                },
            )

        badge, _ = Badge.objects.get_or_create(
            slug="first-steps",
            defaults={
                "name": "First Steps",
                "description": "Completed your first lesson milestone.",
            },
        )

        # Ensure Bounty Hunter badge exists
        bounty_badge, _ = Badge.objects.get_or_create(
            slug="bounty-hunter",
            defaults={
                "name": "Bounty Hunter",
                "description": "Completed open-source practice bounties.",
                "category": "bounties",
            }
        )

        # Seed educational bounties
        bounties_data = [
            {
                "title": "Conventional Commits Compliance",
                "description": "Open-source projects enforce strict standards for commit messages to ensure clean changelogs. In this bounty, your goal is to correct a contributor's commit history to conform to Conventional Commits guidelines (e.g., using prefixes like 'feat:', 'fix:', 'docs:', 'chore:'). Learn how conventional formatting helps maintainers parse history automatically.",
                "xp_reward": 100,
                "badge": bounty_badge,
            },
            {
                "title": "Git Rebase & Commit Squashing",
                "description": "A contributor opened a PR, but it has 8 small, messy commits like 'fixed bug', 'typo', 'testing again'. A maintainer asked them to squash these into a single clean commit. Refactor the branch commit history using git rebase -i to squash all commits into a single clean commit titled 'feat: implement token caching on client'.",
                "xp_reward": 150,
                "badge": bounty_badge,
            },
            {
                "title": "Resolve Git Merge Conflict in Index Page",
                "description": "Upstream changes on the 'main' branch have introduced a merge conflict on 'index.html'. Merge the latest 'main' branch into your feature branch, resolve the conflict markings (<<<<<<<, =======, >>>>>>>), verify that the HTML layout remains clean, and commit your resolved code.",
                "xp_reward": 200,
                "badge": bounty_badge,
            },
            {
                "title": "Parameterize Raw SQL Query (SQL Injection)",
                "description": "Security checks flagged a vulnerability where user-supplied search queries are directly interpolated into a raw SQL query string. Refactor the database query to use query parameterization (or Django ORM filters) to prevent SQL Injection attacks and secure the input fields.",
                "xp_reward": 250,
                "badge": bounty_badge,
            },
            {
                "title": "Write Unit Tests for Date Utilities",
                "description": "Good open-source contributions always include test coverage. The utility module lacks tests for timezone conversion helper functions. Write unit tests using pytest that test standard timezone offsets, daylight savings transitions, and invalid inputs to ensure no future regressions.",
                "xp_reward": 120,
                "badge": bounty_badge,
            },
        ]

        from django.db import transaction
        with transaction.atomic():
            for data in bounties_data:
                bounty, created = Bounty.objects.get_or_create(
                    title=data["title"],
                    defaults={
                        "description": data["description"],
                        "xp_reward": data["xp_reward"],
                        "status": Bounty.Status.OPEN,
                        "badge": data["badge"],
                    }
                )
                if not created:
                    bounty.description = data["description"]
                    bounty.xp_reward = data["xp_reward"]
                    bounty.status = Bounty.Status.OPEN
                    bounty.badge = data["badge"]
                    bounty.save()

        self.stdout.write(self.style.SUCCESS("Database seeding complete!"))
