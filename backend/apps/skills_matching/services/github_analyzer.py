"""
GitHub profile analyzer for contributor skills.
"""

import requests
from typing import Dict, Any, List, Optional
from django.conf import settings
from apps.skill_matching.models import ContributorProfile, SkillTag
import logging

logger = logging.getLogger(__name__)


class GitHubAnalyzer:
    """
    Analyze GitHub profiles for skill extraction.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or getattr(settings, "GITHUB_TOKEN", None)
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    def analyze_user(self, username: str) -> Dict[str, Any]:
        """
        Analyze GitHub user profile.
        """
        user_data = self._fetch_user(username)
        repos = self._fetch_repos(username)
        languages = self._extract_languages(repos)
        commit_count = self._get_commit_count(username)

        # Determine skill levels
        skill_levels = self._determine_skill_levels(languages, repos)

        # Extract frameworks
        frameworks = self._extract_frameworks(repos)

        return {
            "username": username,
            "user_data": user_data,
            "languages": list(languages.keys()),
            "skill_levels": skill_levels,
            "frameworks": frameworks,
            "total_commits": commit_count,
            "total_repos": len(repos),
            "years_experience": self._calculate_experience(user_data),
        }

    def _fetch_user(self, username: str) -> Dict:
        """Fetch user data from GitHub API."""
        response = requests.get(
            f"{self.base_url}/users/{username}", headers=self.headers
        )
        if response.status_code == 200:
            return response.json()
        return {}

    def _fetch_repos(self, username: str) -> List[Dict]:
        """Fetch user repositories."""
        repos = []
        page = 1
        while True:
            response = requests.get(
                f"{self.base_url}/users/{username}/repos",
                headers=self.headers,
                params={"page": page, "per_page": 100},
            )
            if response.status_code != 200 or not response.json():
                break
            repos.extend(response.json())
            page += 1
        return repos

    def _extract_languages(self, repos: List[Dict]) -> Dict[str, int]:
        """Extract languages from repositories."""
        languages = {}
        for repo in repos:
            lang = repo.get("language")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
        return languages

    def _extract_frameworks(self, repos: List[Dict]) -> List[str]:
        """Extract frameworks from repository data."""
        frameworks = set()
        framework_patterns = {
            "react": ["react", "next.js", "gatsby"],
            "django": ["django", "drf"],
            "vue": ["vue", "nuxt"],
            "angular": ["angular"],
            "flask": ["flask"],
            "fastapi": ["fastapi"],
            "node": ["node", "express", "nestjs"],
            "tensorflow": ["tensorflow", "keras"],
            "pytorch": ["pytorch"],
        }

        for repo in repos:
            topics = repo.get("topics", [])
            for framework, patterns in framework_patterns.items():
                for pattern in patterns:
                    if any(pattern in topic for topic in topics):
                        frameworks.add(framework)

        return list(frameworks)

    def _determine_skill_levels(
        self, languages: Dict[str, int], repos: List[Dict]
    ) -> Dict[str, str]:
        """Determine skill levels based on language usage."""
        skill_levels = {}
        total_repos = len(repos)

        for lang, count in languages.items():
            percentage = (count / total_repos) * 100 if total_repos > 0 else 0

            if percentage > 40:
                skill_levels[lang] = "expert"
            elif percentage > 20:
                skill_levels[lang] = "advanced"
            elif percentage > 10:
                skill_levels[lang] = "intermediate"
            else:
                skill_levels[lang] = "beginner"

        return skill_levels

    def _get_commit_count(self, username: str) -> int:
        """Get total commit count (simplified)."""
        # In production, use GitHub's contribution API
        return 0

    def _calculate_experience(self, user_data: Dict) -> float:
        """Calculate years of experience from user data."""
        created_at = user_data.get("created_at")
        if created_at:
            from datetime import datetime

            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            years = (datetime.now() - created).days / 365
            return max(0, years)
        return 0.0
