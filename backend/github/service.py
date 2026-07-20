import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from .auth import get_github_token


class GithubService:
    """Service for interacting with Github API using App Installation Tokens"""

    def __init__(self):
        self.base_url = "https://api.github.com"
        self.token = None
        self._refresh_token()

    def _refresh_token(self):
        """Refresh the access token"""
        self.token = get_github_token()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests"""
        if not self.token:
            self._refresh_token()
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a GitHub API request"""
        # Ensure endpoint is a relative path to prevent SSRF via URL injection
        parsed_endpoint = urlparse(endpoint)
        if parsed_endpoint.scheme or parsed_endpoint.netloc:
            raise ValueError("Invalid endpoint: Must be a relative path")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        parsed_url = urlparse(url)
        if parsed_url.netloc != "api.github.com" and not parsed_url.netloc.endswith(".github.com"):
            raise ValueError("Invalid endpoint: Domain must be a github.com domain")

        headers = self._get_headers()
        headers.update(kwargs.pop("headers", {}))

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Only attempt the 401-refresh-and-retry path if we actually got
            # a response back (connection-level failures like ConnectionError
            # or Timeout never produce a response object).
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code == 401:
                self._refresh_token()
                headers = self._get_headers()
                response = requests.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()
            raise

    def get_user(self, username: str) -> Dict[str, Any]:
        """Get user information"""
        return self.make_request("GET", f"/users/{username}")

    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information"""
        return self.make_request("GET", f"/repos/{owner}/{repo}")

    def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> Dict[str, Any]:
        """Create a comment on an issue"""
        return self.make_request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request information"""
        return self.make_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")

    def create_pull_request_review(
        self, owner: str, repo: str, pr_number: int, **kwargs
    ) -> Dict[str, Any]:
        """Create a review on a pull request"""
        return self.make_request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", json=kwargs
        )


# Singleton instance
github_service = GithubService()
