"""
Management command to seed the database with sample TriageIssue scenarios.

Usage:
    python manage.py seed_triage_issues
"""

from django.core.management.base import BaseCommand

from apps.sandbox.models import TriageIssue


SAMPLE_ISSUES = [
    {
        "title": "Scenario 1: Missing Steps to Reproduce",
        "raw_issue_title": "The app crashes!!",
        "raw_issue_body": (
            "I was using the app and it crashed. Idk why. "
            "Please fix ASAP!!!! This is really annoying."
        ),
        "correct_labels": ["bug", "needs-repro"],
        "model_response": (
            "Thank you for opening this issue! We appreciate you taking the time to report this.\n\n"
            "To help us investigate the crash, could you please provide the following information?\n"
            "1. **Steps to reproduce** – What were you doing exactly when the crash occurred?\n"
            "2. **Environment** – What operating system and browser/app version are you using?\n"
            "3. **Expected behavior** – What did you expect to happen?\n"
            "4. **Actual behavior** – What actually happened? Any error messages or stack traces?\n\n"
            "Once we have these details, we'll be able to look into this much more quickly. "
            "Hope to hear from you soon!"
        ),
        "hint": (
            "The report has no steps to reproduce or environment details. "
            "It is clearly a bug, but needs more info before it can be worked on."
        ),
        "difficulty": "easy",
    },
    {
        "title": "Scenario 2: Feature Request Disguised as a Bug",
        "raw_issue_title": "dark mode doesnt work",
        "raw_issue_body": (
            "why is there no dark mode?? every modern app has dark mode. "
            "my eyes hurt. add dark mode please. "
            "environment: chrome on windows 11, app version 2.4.1"
        ),
        "correct_labels": ["enhancement"],
        "model_response": (
            "Hi there! Thanks for the suggestion — we appreciate the feedback!\n\n"
            "This sounds like a feature request for a dark mode rather than a bug with existing "
            "functionality. We've relabelled it as an enhancement.\n\n"
            "Could you share any particular pages or components where dark mode would be most "
            "impactful for you? That will help us prioritize the work.\n\n"
            "We welcome contributions too — if you'd like to tackle this, check out our "
            "CONTRIBUTING.md guide!"
        ),
        "hint": (
            "Dark mode doesn't exist yet — this is not a bug, it's a feature request. "
            "The correct label is 'enhancement', not 'bug'."
        ),
        "difficulty": "easy",
    },
    {
        "title": "Scenario 3: Already Reported / Duplicate Issue",
        "raw_issue_title": "Login button not working on mobile",
        "raw_issue_body": (
            "When I tap the login button on my iPhone (iOS 17, Safari), nothing happens. "
            "The page just refreshes but I don't get logged in. "
            "Tried clearing cache, same issue. "
            "Happens on version 3.1.0."
        ),
        "correct_labels": ["bug", "duplicate"],
        "model_response": (
            "Thank you for the detailed report — you've provided all the right information!\n\n"
            "It looks like this is a duplicate of #482, which tracks the same Safari/iOS login "
            "regression introduced in v3.1.0. We're actively working on a fix.\n\n"
            "I'll close this in favour of #482 to keep the discussion centralised, "
            "but please feel free to follow along there and add any additional context."
        ),
        "hint": (
            "This is a well-written bug report. Check the existing issues — "
            "a nearly identical report for Safari/iOS login exists. The correct labels are 'bug' and 'duplicate'."
        ),
        "difficulty": "medium",
    },
    {
        "title": "Scenario 4: Security Vulnerability Report",
        "raw_issue_title": "I can see other users' private data through the API",
        "raw_issue_body": (
            "Hi, I found that if I change the user_id parameter in the GET /api/users/{id}/ "
            "endpoint to another user's ID, I can see their private profile data including "
            "their email and phone number. I tested this on the staging server. "
            "OS: macOS Ventura, Chrome 120. App version: latest."
        ),
        "correct_labels": ["bug", "invalid"],
        "model_response": (
            "Thank you for responsibly bringing this to our attention!\n\n"
            "This appears to be a potential security vulnerability. "
            "**Please do not share further details publicly.** We ask that you "
            "report security issues via our private security disclosure process at "
            "security@example.com as per our SECURITY.md.\n\n"
            "We'll acknowledge your report within 48 hours and keep you updated on our findings. "
            "We sincerely appreciate responsible disclosure."
        ),
        "hint": (
            "This is a security vulnerability / IDOR (Insecure Direct Object Reference). "
            "It's technically a bug, but should be handled through the private security channel, "
            "not the public tracker. Label it 'bug'. The 'invalid' label should NOT be used here."
        ),
        "difficulty": "hard",
    },
    {
        "title": "Scenario 5: Documentation Gap",
        "raw_issue_title": "How do I configure the webhook secret?",
        "raw_issue_body": (
            "I've been trying to set up webhooks for 2 hours. "
            "The README says to set WEBHOOK_SECRET but doesn't say where or how. "
            "I looked through the settings but couldn't find it. "
            "Can someone please explain how this is supposed to work?"
        ),
        "correct_labels": ["question", "documentation"],
        "model_response": (
            "Thanks for opening this — you're right that the documentation is unclear here, "
            "and we'll improve it!\n\n"
            "In the meantime, to configure the webhook secret:\n"
            "1. Copy `.env.example` to `.env` in the project root.\n"
            "2. Set `WEBHOOK_SECRET=your-secret-here` in the `.env` file.\n"
            "3. Restart the server.\n\n"
            "The webhook endpoint will now validate incoming payloads against this secret. "
            "Does this help? If so, feel free to close this issue or we can track the "
            "documentation improvement separately."
        ),
        "hint": (
            "This is a usage question, not a bug. The user is confused because the documentation "
            "is missing details. Correct labels: 'question' and 'documentation'."
        ),
        "difficulty": "medium",
    },
]


class Command(BaseCommand):
    help = "Seed the database with sample TriageIssue scenarios for Feature 11."

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for data in SAMPLE_ISSUES:
            obj, created = TriageIssue.objects.get_or_create(
                title=data["title"],
                defaults={
                    "raw_issue_title": data["raw_issue_title"],
                    "raw_issue_body": data["raw_issue_body"],
                    "correct_labels": data["correct_labels"],
                    "model_response": data["model_response"],
                    "hint": data["hint"],
                    "difficulty": data["difficulty"],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {obj.title}"))
            else:
                skipped_count += 1
                self.stdout.write(f"  Skipped (already exists): {obj.title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created {created_count} scenario(s), skipped {skipped_count}."
            )
        )
