from apps.progress.models import Badge, UserBadge, LessonProgress

BADGE_RULES = {
    "first-steps": {
        "name": "First Steps",
        "description": "Completed your first lesson.",
        "min_lessons": 1,
    },
    "mod-1": {
        "name": "Open Source Explorer",
        "description": "Understand open source mindset and history.",
        "lessons": [
            "what-is-open-source",
            "why-open-source-matters",
            "history-of-open-source",
            "benefits-of-contributing",
            "common-misconceptions",
        ],
    },
    "mod-2": {
        "name": "Git Cadet",
        "description": "Initialize repos, commit, and manage local branches.",
        "lessons": [
            "repositories-and-commits",
            "branches",
            "merging",
            "remotes",
            "git-workflow",
        ],
    },
    "mod-3": {
        "name": "GitHub Knight",
        "description": "Master forks, issues, PRs, and team organizations.",
        "lessons": [
            "github-repositories",
            "forks",
            "pull-requests",
            "issues",
            "discussions",
            "organizations",
        ],
    },
    "mod-4": {
        "name": "Etiquette Master",
        "description": "Practice professional communication and PR workflows.",
        "lessons": [
            "respect-and-communication",
            "read-readme-and-contributing",
            "professional-prs-and-issues",
            "maintainer-review-processes",
        ],
    },
    "mod-5": {
        "name": "First Merge",
        "description": "Practice local-upstream commit pushing.",
        "lessons": [
            "first-contribution-walkthrough",
        ],
    },
    "mod-6": {
        "name": "Workflow Champion",
        "description": "Understand issue life-cycle management.",
        "lessons": [
            "contribution-lifecycle",
        ],
    },
    "mod-7": {
        "name": "Rebase Sensei",
        "description": "Rebase, resolve conflicts, and parse CI/CD checks.",
        "lessons": [
            "rebasing-and-squashing",
            "conflict-resolution",
            "code-reviews-and-cicd",
        ],
    },
    "mod-8": {
        "name": "Hacktoberfest Ready",
        "description": "Find beginner-friendly repositories and issues.",
        "lessons": [
            "finding-projects",
        ],
    },
    "grad": {
        "name": "Atelier Graduate",
        "description": "Complete 100% of the learning program.",
        "lessons": [
            "what-is-open-source",
            "why-open-source-matters",
            "history-of-open-source",
            "benefits-of-contributing",
            "common-misconceptions",
            "repositories-and-commits",
            "branches",
            "merging",
            "remotes",
            "git-workflow",
            "github-repositories",
            "forks",
            "pull-requests",
            "issues",
            "discussions",
            "organizations",
            "respect-and-communication",
            "read-readme-and-contributing",
            "professional-prs-and-issues",
            "maintainer-review-processes",
            "first-contribution-walkthrough",
            "contribution-lifecycle",
            "rebasing-and-squashing",
            "conflict-resolution",
            "code-reviews-and-cicd",
            "finding-projects",
        ],
    },
}

class BadgeEvaluator:
    @classmethod
    def evaluate(cls, user):
        if not user or not user.is_authenticated:
            return

        # Fetch user's completed lesson slugs
        completed_slugs = set(
            LessonProgress.objects.filter(user=user, completed=True)
            .values_list("lesson__slug", flat=True)
        )

        # Fetch user's already earned badge slugs
        earned_slugs = set(
            UserBadge.objects.filter(user=user).values_list("badge__slug", flat=True)
        )

        for badge_slug, rule in BADGE_RULES.items():
            if badge_slug in earned_slugs:
                continue

            # Evaluate the rule
            meets_criteria = False
            if "min_lessons" in rule:
                meets_criteria = len(completed_slugs) >= rule["min_lessons"]
            elif "lessons" in rule:
                meets_criteria = all(slug in completed_slugs for slug in rule["lessons"])

            if meets_criteria:
                badge, _ = Badge.objects.get_or_create(
                    slug=badge_slug,
                    defaults={
                        "name": rule["name"],
                        "description": rule["description"]
                    }
                )
                UserBadge.objects.get_or_create(user=user, badge=badge)
