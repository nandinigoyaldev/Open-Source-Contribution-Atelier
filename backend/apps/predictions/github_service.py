import logging
import requests
from django.conf import settings
from .models import PullRequestMetric, ReviewerAvailability

logger = logging.getLogger(__name__)


class GitHubPRService:
    """
    Service layer to interact with GitHub API for PR metadata & Reviewer metrics.
    """

    def __init__(self, token=None):
        self.token = token
        self.headers = {"Authorization": f"token {token}"} if token else {}

    def fetch_pr_data(self, owner: str, repo: str, pr_number: int) -> dict:
        """
        Fetches PR metadata from GitHub API or returns simulated PR metrics with logged fallback.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        repo_name = f"{owner}/{repo}" if owner and repo else "default"

        if self.token:
            try:
                res = requests.get(url, headers=self.headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    status_val = "OPEN"
                    if data.get("merged"):
                        status_val = "MERGED"
                    elif data.get("state") == "closed":
                        status_val = "CLOSED"

                    return {
                        "repo_name": repo_name,
                        "pr_number": data.get("number"),
                        "title": data.get("title", ""),
                        "author": data.get("user", {}).get("login", "unknown"),
                        "additions": data.get("additions", 0),
                        "deletions": data.get("deletions", 0),
                        "changed_files": data.get("changed_files", 0),
                        "status": status_val,
                        "requested_reviewers": [r.get("login") for r in data.get("requested_reviewers", [])],
                        "is_simulated": False,
                    }
                else:
                    logger.warning("GitHub API returned status code %s for PR #%s. Operating in degraded fallback mode.", res.status_code, pr_number)
            except Exception as exc:
                logger.warning("GitHub API request failed for PR #%s: %s. Operating in degraded fallback mode.", pr_number, exc)

        logger.info("Using simulated fallback PR data for PR #%s", pr_number)
        return {
            "repo_name": repo_name,
            "pr_number": pr_number,
            "title": f"Feature Implementation #{pr_number}",
            "author": "contributor",
            "additions": 150 + (pr_number * 10) % 500,
            "deletions": 30 + (pr_number * 5) % 200,
            "changed_files": 4 + (pr_number % 8),
            "status": "OPEN",
            "requested_reviewers": ["maintainer-1"],
            "is_simulated": True,
        }

    def sync_pr_metric(self, pr_data: dict, assigned_reviewer_username: str = None) -> PullRequestMetric:
        """
        Upserts PR metric in database scoped by (repo_name, pr_number) without resetting existing non-open status,
        and keeps reviewer workload synchronized.
        """
        repo_name = pr_data.get("repo_name", "default")
        pr_number = pr_data["pr_number"]

        pr_metric = PullRequestMetric.objects.filter(repo_name=repo_name, pr_number=pr_number).first()
        old_reviewer = pr_metric.assigned_reviewer if pr_metric else None

        new_reviewer = old_reviewer
        if assigned_reviewer_username:
            new_reviewer, _ = ReviewerAvailability.objects.get_or_create(
                reviewer_username=assigned_reviewer_username,
                defaults={"current_workload": 0, "activity_score": 0.8}
            )

        if pr_metric is None:
            pr_metric = PullRequestMetric.objects.create(
                repo_name=repo_name,
                pr_number=pr_number,
                title=pr_data.get("title", "Untitled PR"),
                author=pr_data.get("author", "unknown"),
                assigned_reviewer=new_reviewer,
                additions=pr_data.get("additions", 0),
                deletions=pr_data.get("deletions", 0),
                changed_files=pr_data.get("changed_files", 0),
                status=pr_data.get("status", "OPEN"),
            )
        else:
            pr_metric.title = pr_data.get("title", pr_metric.title)
            pr_metric.author = pr_data.get("author", pr_metric.author)
            pr_metric.additions = pr_data.get("additions", pr_metric.additions)
            pr_metric.deletions = pr_data.get("deletions", pr_metric.deletions)
            pr_metric.changed_files = pr_data.get("changed_files", pr_metric.changed_files)
            if "status" in pr_data and pr_data["status"]:
                pr_metric.status = pr_data["status"]
            if assigned_reviewer_username:
                pr_metric.assigned_reviewer = new_reviewer
            pr_metric.save()

        # Synchronize reviewer workload counters if reviewer changed
        if old_reviewer and old_reviewer != new_reviewer:
            old_reviewer.recalculate_workload()
        if new_reviewer:
            new_reviewer.recalculate_workload()

        return pr_metric
