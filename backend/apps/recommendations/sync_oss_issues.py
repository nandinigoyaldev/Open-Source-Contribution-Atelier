import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.recommendations.models import OSSIssue


class Command(BaseCommand):
    help = "Sync OSS issues from GitHub API"

    def handle(self, *args, **options):
        self.stdout.write("🔄 Syncing OSS issues from GitHub...")

        # GitHub API config
        GITHUB_TOKEN = getattr(settings, "GITHUB_TOKEN", None)
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        # Search for good first issues
        url = "https://api.github.com/search/issues"
        params = {
            "q": 'label:"good first issue" is:open',
            "sort": "updated",
            "per_page": 100,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            issues = data.get("items", [])

            for issue in issues:
                # Check rate limit
                remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                if remaining == 0:
                    self.stdout.write(self.style.WARNING("⚠️ Rate limit reached"))
                    break

                # Deduplicate
                OSSIssue.objects.update_or_create(
                    github_id=issue["id"],
                    defaults={
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "repo": issue["repository"]["full_name"],
                        "labels": [label["name"] for label in issue["labels"]],
                        "is_open": True,
                    },
                )

            self.stdout.write(self.style.SUCCESS(f"✅ Synced {len(issues)} issues"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Sync failed: {e}"))
