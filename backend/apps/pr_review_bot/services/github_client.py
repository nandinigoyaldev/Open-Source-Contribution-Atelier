"""
GitHub API client for PR interactions.
"""

import requests
from typing import Dict, Any, List
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class GitHubClient:
    """
    GitHub API client for PR operations.
    """

    def __init__(self):
        self.token = getattr(settings, "GITHUB_TOKEN", None)
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict]:
        """
        Get files changed in PR.
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        return []

    def post_review_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
        commit_id: str = None,
        file_path: str = None,
        line_number: int = None,
    ) -> Dict:
        """
        Post a review comment on PR.
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/comments"

        data = {"body": body}

        if commit_id:
            data["commit_id"] = commit_id
        if file_path:
            data["path"] = file_path
        if line_number:
            data["line"] = line_number

        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def post_review(
        self, repo: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> Dict:
        """
        Post a full review on PR.
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/reviews"
        data = {"body": body, "event": event}

        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def get_pr_info(self, repo: str, pr_number: int) -> Dict:
        """
        Get PR information.
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        return {}
