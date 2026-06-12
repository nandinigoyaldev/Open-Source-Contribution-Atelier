from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.dashboard.models import Issue, PullRequest
from apps.content.models import Lesson, Exercise
from apps.progress.models import LessonProgress, ExerciseAttempt


class Command(BaseCommand):
    help = "Seeds the database with robust mock data for the role-based dashboard charts and stats."

    def handle(self, *args, **options):
        self.stdout.write("Seeding data for The Maintainer Atelier...")

        # 1. Create Users
        self.stdout.write("- Creating Admin & Contributors...")
        
        # Admin
        admin, created = User.objects.get_or_create(username="admin", email="admin@atelier.com")
        admin.set_password("password123")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self.stdout.write(f"  Admin: {admin.username} ({'created' if created else 'updated'})")

        # Contributors
        contributors_data = [
            ("alice", "alice@example.com"),
            ("bob", "bob@example.com"),
            ("charlie", "charlie@example.com"),
            ("diana", "diana@example.com"),
        ]
        contributors = []
        for username, email in contributors_data:
            user, c_created = User.objects.get_or_create(username=username, email=email)
            user.set_password("password123")
            user.is_staff = False
            user.is_superuser = False
            user.save()
            contributors.append(user)
            self.stdout.write(f"  Contributor: {user.username} ({'created' if c_created else 'updated'})")

        # 2. Create Lessons
        self.stdout.write("- Creating Lessons & Curriculum...")
        lessons_data = [
            ("Introduction to open-source", "intro-os", "Welcome to open source. Learn issues, forks, clones, and etiquette.", 10),
            ("Mastering local Git branches", "git-branches", "Deep dive into local branch models, HEAD staging.", 15),
            ("Making pull requests with ease", "make-prs", "Create branch, make changes, commit, push, and open pull request.", 15),
            ("Resolving scary conflicts", "git-conflicts", "Learn how to read three-way diff marks and safely resolve conflicts.", 20),
            ("Clean commits & Rebase flows", "git-rebase", "Practice safe commit squashing, interactive rebases, and clean trees.", 25),
        ]
        lessons = []
        exercises = {}
        for i, (title, slug, summary, duration) in enumerate(lessons_data):
            lesson, l_created = Lesson.objects.get_or_create(slug=slug)
            lesson.title = title
            lesson.summary = summary
            lesson.estimated_minutes = duration
            lesson.order = i
            lesson.save()
            lessons.append(lesson)
            
            # Create an exercise linked to the lesson
            exercise, _ = Exercise.objects.get_or_create(
                lesson=lesson,
                title=f"Exercise: {title}",
                defaults={
                    "prompt": f"Emulate the command required to complete: {title}",
                    "expected_command": "git status",
                    "explanation": "Complete the actions as outlined in the lessons.",
                    "points": 10
                }
            )
            exercises[lesson.slug] = exercise
            self.stdout.write(f"  Lesson: {lesson.title} (with Exercise)")

        # 3. Create Lesson Progress (mock XP scores)
        self.stdout.write("- Simulating Contributor curriculum learning progress...")
        # Alice is highly active, completes almost everything
        # Bob is medium active
        # Charlie completed a couple
        # Diana just registered, completes none
        progress_profiles = {
            "alice": [0, 1, 2, 3],
            "bob": [0, 1, 2],
            "charlie": [0, 1],
            "diana": []
        }
        
        for contributor in contributors:
            completed_indices = progress_profiles.get(contributor.username, [])
            for idx in completed_indices:
                lesson = lessons[idx]
                lp, _ = LessonProgress.objects.get_or_create(user=contributor, lesson=lesson)
                lp.completed = True
                lp.score = random.randint(100, 150)
                lp.updated_at = timezone.now() - timedelta(days=random.randint(1, 10))
                lp.save()
                
                # Create some exercise attempts for streak calculation
                ExerciseAttempt.objects.create(
                    user=contributor,
                    exercise=exercises[lesson.slug],
                    submitted_command="git commit -m 'feat: add stuff'",
                    is_correct=True,
                    created_at=lp.updated_at
                )

        # 4. Create Issues
        self.stdout.write("- Creating repository Issues...")
        issues_data = [
            ("Fix dark mode contrast in forms", "Make forms readable in dark mode.", Issue.Status.SOLVED, 50, "alice"),
            ("Implement simple token caching on client", "Avoid extra fetch calls by caching tokens in localStorage.", Issue.Status.SOLVED, 100, "alice"),
            ("Add validation schema for user signup", "Ensure usernames are safe alphanumeric characters.", Issue.Status.IN_PROGRESS, 75, "bob"),
            ("Write mock endpoints for profile sandbox", "Prepare mock structures to emulate shell operations.", Issue.Status.OPEN, 60, "bob"),
            ("Fix broken link in Navigation sidebar", "Update old relative path to dashboard routes.", Issue.Status.SOLVED, 30, "charlie"),
            ("Refactor dashboard widgets to grid structure", "Improve responsiveness of analytics cards.", Issue.Status.OPEN, 80, None),
            ("Document Docker deployment workflow", "Add section in wiki explaining compose production setups.", Issue.Status.OPEN, 50, None),
        ]
        
        issues = []
        for title, desc, status, points, assigned_username in issues_data:
            assigned_user = User.objects.filter(username=assigned_username).first() if assigned_username else None
            issue, _ = Issue.objects.get_or_create(title=title)
            issue.description = desc
            issue.status = status
            issue.points = points
            issue.assigned_to = assigned_user
            issue.save()
            issues.append(issue)
            self.stdout.write(f"  Issue: {issue.title} ({issue.status})")

        # 5. Create Pull Requests
        self.stdout.write("- Simulating practice Pull Requests submissions...")
        # Link PRs to issues and contributors
        prs_data = [
            ("feat: solve dark mode contrast issues", PullRequest.Status.MERGED, issues[0], "alice", 1),
            ("feat: add token localStorage cache", PullRequest.Status.MERGED, issues[1], "alice", 2),
            ("docs: fix navigation links to dashboard", PullRequest.Status.MERGED, issues[4], "charlie", 3),
            ("feat: add signup regex validator", PullRequest.Status.OPEN, issues[2], "bob", 0),
            ("chore: update README deploy instructions", PullRequest.Status.CLOSED, None, "charlie", 4),
            ("feat: dockerize atelier container stack", PullRequest.Status.OPEN, None, "bob", 0),
        ]

        for title, pr_status, issue, username, days_ago in prs_data:
            user = User.objects.filter(username=username).first()
            pr, _ = PullRequest.objects.get_or_create(title=title, user=user)
            pr.status = pr_status
            pr.issue = issue
            pr.created_at = timezone.now() - timedelta(days=days_ago)
            if pr_status == PullRequest.Status.MERGED:
                pr.merged_at = pr.created_at + timedelta(hours=random.randint(1, 24))
            pr.save()
            self.stdout.write(f"  PR: {pr.title} ({pr.status})")

        self.stdout.write(self.style.SUCCESS("Atelier dashboard data seeded successfully! 🎉"))
        self.stdout.write(self.style.SUCCESS("Demo credentials: Username: 'admin' or 'alice' or 'bob' · Password: 'password123'"))
