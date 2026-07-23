import jwt
import requests
import time
import os
from typing import Optional
from datetime import datetime, timedelta, timezone
from django.core.cache import cache


class GitHubAppAuth:
    """Handles GitHub App authentication using installation tokens"""

    def __init__(self):
        self.app_id = os.getenv("GITHUB_APP_ID")
        self.private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
        self.installation_id = os.getenv("GITHUB_INSTALLATION_ID")
        self.cache_key = "github_installation_token"

    def generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication"""
        if not self.app_id or not self.private_key_path:
            raise ValueError("GitHub App credentials not configured")

        try:
            with open(self.private_key_path, "r") as f:
                private_key = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Private key not found at {self.private_key_path}")

        # JWT payload
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + (10 * 60),  # 10 minutes expiration
            "iss": self.app_id,
        }

        # Generate JWT
        headers = {
            "alg": "RS256",
            "typ": "JWT",
        }

        return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)

    def get_installation_token(self) -> Optional[str]:
        """Get an installation access token for the GitHub App"""
        if not self.installation_id:
            raise ValueError("GITHUB_INSTALLATION_ID not configured")

        cached_token = cache.get(self.cache_key)
        if cached_token:
            return cached_token

        jwt_token = self.generate_jwt()

        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            token = data.get("token")
            expires_at = data.get("expires_at")

            # Cache token with 10 minute buffer
            if token and expires_at:
                expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                ttl = int((expires - datetime.now(timezone.utc)).total_seconds()) - 600
                if ttl > 0:
                    cache.set(self.cache_key, token, ttl)

            return token
        except requests.exceptions.RequestException as e:
            print(f"Failed to get installation token: {e}")
            return None

    def refresh_token(self) -> Optional[str]:
        """Force refresh the installation token"""
        cache.delete(self.cache_key)
        return self.get_installation_token()


# Singleton instance
github_auth = GitHubAppAuth()


def get_github_token() -> Optional[str]:
    """Convenience function to get GitHub token"""
    return github_auth.get_installation_token()


def refresh_github_token() -> Optional[str]:
    """Convenience function to refresh GitHub token"""
    return github_auth.refresh_token()
