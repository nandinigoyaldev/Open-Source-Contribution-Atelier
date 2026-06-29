from apps.content.models import Exercise, Lesson
from django.core.management.base import BaseCommand

from typing import Any, Dict, List

LESSONS: List[Dict[str, Any]] = [
    {
        "slug": "intro",
        "category": "basics",
        "difficulty": "beginner",
        "title": "Open Source Mindset",
        "summary": "Understand how open source collaboration actually works.",
        "content": "Open source is not only about code. It includes communication, issue triage, reviews, and consistency. In this track, you will practice the same workflow maintainers expect on real projects.",
        "learning_objectives": [
            "Explain what makes a good first contribution",
            "Understand maintainers vs contributors responsibilities",
            "Identify where to start in an unfamiliar repository",
        ],
        "tips": [
            "Read README and CONTRIBUTING before writing code.",
            "Small, focused pull requests get merged faster.",
            "Good communication is as important as good code.",
        ],
        "order": 0,
        "estimated_minutes": 8,
        "exercises": [
            {
                "title": "Reflect on workflow",
                "prompt": "Type: open-source means collaboration",
                "expected_command": "open-source means collaboration",
                "explanation": "This confirms you understand the core idea before Git mechanics.",
                "points": 5,
            }
        ],
    },
    {
        "slug": "clone-and-setup",
        "category": "basics",
        "difficulty": "beginner",
        "title": "Clone and Setup",
        "summary": "Clone a project and inspect the working tree.",
        "content": "The first practical step is cloning and understanding repo state. Use status often; it is your primary source of truth.",
        "learning_objectives": [
            "Clone repositories correctly",
            "Use git status to inspect branch and file state",
            "Recognize clean vs dirty working trees",
        ],
        "tips": [
            "Run git status before and after each significant action.",
            "Never assume current branch; check it.",
        ],
        "order": 1,
        "estimated_minutes": 10,
        "exercises": [
            {
                "title": "Check repository state",
                "prompt": "Run the command that shows working tree status.",
                "expected_command": "git status",
                "explanation": "`git status` helps avoid accidental commits and branch mistakes.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "branching-basics",
        "category": "git-workflow",
        "difficulty": "beginner",
        "title": "Branching Basics",
        "summary": "Create a branch for isolated work.",
        "content": "Never work directly on main. Create feature branches with clear names so reviewers immediately understand purpose.",
        "learning_objectives": [
            "Create a new branch from main",
            "Use predictable branch naming",
            "Avoid direct commits on main",
        ],
        "tips": [
            "Use prefixes like feat/, fix/, docs/.",
            "Keep branch scope focused to one goal.",
        ],
        "order": 2,
        "estimated_minutes": 10,
        "exercises": [
            {
                "title": "Create feature branch",
                "prompt": "Create and switch to branch feat/add-readme-badges.",
                "expected_command": "git switch -c feat/add-readme-badges",
                "explanation": "Use `git switch -c` for creating and moving to a branch.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "staging-and-commits",
        "category": "git-workflow",
        "difficulty": "beginner",
        "title": "Staging and Commits",
        "summary": "Stage targeted files and write clean commit messages.",
        "content": "Commit history is communication for maintainers and future contributors. Stage intentionally and keep messages explicit.",
        "learning_objectives": [
            "Stage only intended files",
            "Write actionable commit messages",
            "Separate unrelated changes into distinct commits",
        ],
        "tips": [
            "Avoid `git add .` on unfamiliar repos.",
            "Use imperative messages like 'Add issue labels'.",
        ],
        "order": 3,
        "estimated_minutes": 12,
        "exercises": [
            {
                "title": "Commit with good message",
                "prompt": "Create a commit with message Add contribution checklist.",
                "expected_command": 'git commit -m "Add contribution checklist"',
                "explanation": "Descriptive commits make review and rollback easier.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "sync-and-rebase",
        "category": "git-workflow",
        "difficulty": "intermediate",
        "title": "Sync and Rebase",
        "summary": "Keep your branch current with upstream changes.",
        "content": "Before opening or updating a PR, synchronize with main. Rebasing keeps history linear and easier to review.",
        "learning_objectives": [
            "Fetch latest remote refs",
            "Rebase branch onto updated main",
            "Resolve simple rebase conflicts",
        ],
        "tips": [
            "Use `git fetch` before rebasing.",
            "If rebasing feels risky, create a backup branch first.",
        ],
        "order": 4,
        "estimated_minutes": 14,
        "exercises": [
            {
                "title": "Fetch remote updates",
                "prompt": "Fetch latest changes from remote.",
                "expected_command": "git fetch origin",
                "explanation": "Fetching updates remote-tracking branches without changing your files.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "push-and-pr",
        "category": "collaboration",
        "difficulty": "intermediate",
        "title": "Push and Pull Request",
        "summary": "Publish your branch and create a reviewable PR.",
        "content": "Push your branch with upstream tracking so future pushes are clean. Then open a PR with context, checklist, and testing notes.",
        "learning_objectives": [
            "Push branch with upstream",
            "Create PR with clear summary",
            "Reference related issues in PR description",
        ],
        "tips": [
            "Use `Closes #issue-number` when applicable.",
            "Add screenshots for UI changes.",
        ],
        "order": 5,
        "estimated_minutes": 12,
        "exercises": [
            {
                "title": "Push tracking branch",
                "prompt": "Push current branch and set upstream on origin.",
                "expected_command": "git push -u origin feat/add-readme-badges",
                "explanation": "The `-u` flag configures upstream tracking.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "issue-triage",
        "category": "collaboration",
        "difficulty": "intermediate",
        "title": "Issue Triage",
        "summary": "Classify and refine issues so contributors can execute quickly.",
        "content": "Great maintainers shape work before code starts. Good triage includes reproducible steps, labels, severity, and acceptance criteria.",
        "learning_objectives": [
            "Write clear issue scope",
            "Apply labels and difficulty tags",
            "Define acceptance criteria",
        ],
        "tips": [
            "If the issue is too big, split it.",
            "Add links to relevant files and docs.",
        ],
        "order": 6,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Inspect branches before triage",
                "prompt": "List local and remote branches.",
                "expected_command": "git branch -a",
                "explanation": "Helps understand active work before assigning new tasks.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "review-feedback",
        "category": "collaboration",
        "difficulty": "intermediate",
        "title": "Code Review Feedback",
        "summary": "Respond to review comments efficiently and respectfully.",
        "content": "Review is collaboration, not conflict. Clarify intent, apply requested changes, and update commit history where needed.",
        "learning_objectives": [
            "Respond to PR comments constructively",
            "Amend commits when appropriate",
            "Re-run tests before requesting another review",
        ],
        "tips": [
            "Reply on each thread so reviewers know what's resolved.",
            "Avoid force-pushing unexpectedly on shared branches.",
        ],
        "order": 7,
        "estimated_minutes": 12,
        "exercises": [
            {
                "title": "View concise commit history",
                "prompt": "Show compact commit history.",
                "expected_command": "git log --oneline",
                "explanation": "Useful for making sure commits are coherent before final review.",
                "points": 10,
            }
        ],
    },
    {
        "slug": "conflict-resolution",
        "category": "advanced",
        "difficulty": "advanced",
        "title": "Conflict Resolution",
        "summary": "Handle merge conflicts safely.",
        "content": "Conflicts are normal in active projects. Resolve carefully, verify behavior, and communicate what changed.",
        "learning_objectives": [
            "Recognize conflict markers",
            "Resolve and stage conflict files",
            "Continue interrupted rebase safely",
        ],
        "tips": [
            "Use mergetool if manual editing gets messy.",
            "Run tests after conflict resolution.",
        ],
        "order": 8,
        "estimated_minutes": 16,
        "exercises": [
            {
                "title": "Continue rebase after conflicts",
                "prompt": "Continue a rebase after conflict resolution.",
                "expected_command": "git rebase --continue",
                "explanation": "Use this after fixing conflicts and staging files.",
                "points": 12,
            }
        ],
    },
    {
        "slug": "maintainer-habits",
        "category": "advanced",
        "difficulty": "advanced",
        "title": "Maintainer Habits",
        "summary": "Turn your project into an inviting contributor ecosystem.",
        "content": "Healthy OSS projects have predictable processes, documentation, and issue hygiene. Maintenance quality directly impacts contributor velocity.",
        "learning_objectives": [
            "Define contributor onboarding steps",
            "Keep issue backlog healthy",
            "Document release and review expectations",
        ],
        "tips": [
            "Close stale issues with a reason.",
            "Tag newcomer-friendly issues consistently.",
        ],
        "order": 9,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Prune merged branches",
                "prompt": "Delete a local branch after merge.",
                "expected_command": "git branch -d feat/add-readme-badges",
                "explanation": "Keeps local repo clean after completed work.",
                "points": 12,
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the database with example lessons and exercises. Safe to run multiple times."

    def handle(self, *args, **options):
        previous_lesson = None
        for l in LESSONS:
            lesson_obj, _ = Lesson.objects.update_or_create(
                slug=l["slug"],
                defaults={
                    "difficulty": l.get("difficulty", "beginner"),
                    "title": l["title"],
                    "summary": l["summary"],
                    "content": l["content"],
                    "learning_objectives": l.get("learning_objectives", []),
                    "tips": l.get("tips", []),
                    "category": l.get("category", "general"),
                    "order": l.get("order", 0),
                    "estimated_minutes": l.get("estimated_minutes", 15),
                },
            )

            if previous_lesson:
                lesson_obj.prerequisites.add(previous_lesson)
            previous_lesson = lesson_obj

            self.stdout.write(
                self.style.SUCCESS(f"Created/updated lesson: {lesson_obj.slug}")
            )

            exercises = l.get("exercises", [])
            if isinstance(exercises, list):
                for ex in exercises:
                    ex_obj, _ = Exercise.objects.update_or_create(
                        lesson=lesson_obj,
                        title=ex["title"],
                        defaults={
                            "prompt": ex["prompt"],
                            "expected_command": ex.get("expected_command", ""),
                            "explanation": ex.get("explanation", ""),
                            "points": ex.get("points", 10),
                        },
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created/updated exercise: {ex_obj.title}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
