"""
GitHub profile analyzer for skill detection.
"""

import requests
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.contrib.auth.models import User
from apps.recommendations.models import UserSkillProfile

logger = logging.getLogger(__name__)


class GitHubAnalyzer:
    """
    Analyzes GitHub profiles to extract skills and experience.
    """
    
    GITHUB_API_URL = "https://api.github.com"
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or getattr(settings, 'GITHUB_TOKEN', None)
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
        else:
            logger.warning("GITHUB_TOKEN is missing. Requests will be unauthenticated and subject to strict rate limits.")
    
    def analyze_user(self, username: str) -> Dict[str, Any]:
        """
        Analyze a GitHub user's profile.
        
        Args:
            username: GitHub username
        
        Returns:
            Dict: User profile data with skills
        """
        user_data = self._get_user_data(username)
        if not user_data:
            return {}
        
        # Get repositories
        repos = self._get_user_repos(username)
        languages = self._extract_languages(repos)
        commits = self._get_total_commits(username)
        
        # Analyze commit patterns
        commit_patterns = self._analyze_commit_patterns(repos)
        
        # Determine skill levels
        skill_levels = self._determine_skill_levels(languages, commit_patterns)
        
        return {
            'login': user_data.get('login'),
            'name': user_data.get('name'),
            'bio': user_data.get('bio'),
            'total_repos': len(repos),
            'languages': languages,
            'skill_levels': skill_levels,
            'total_commits': commits,
            'frameworks': self._extract_frameworks(repos),
            'contributions': self._get_contributions(username),
        }
    
    def _get_user_data(self, username: str) -> Optional[Dict]:
        """Get user data from GitHub API."""
        try:
            response = requests.get(
                f"{self.GITHUB_API_URL}/users/{username}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user data for {username}: {e}")
            return None
    
    def _get_user_repos(self, username: str) -> List[Dict]:
        """Get user repositories."""
        repos = []
        page = 1
        while True:
            try:
                response = requests.get(
                    f"{self.GITHUB_API_URL}/users/{username}/repos",
                    headers=self.headers,
                    params={'page': page, 'per_page': 100}
                )
                response.raise_for_status()
                data = response.json()
                if not data:
                    break
                repos.extend(data)
                page += 1
            except Exception as e:
                logger.error(f"Failed to get repos for {username}: {e}")
                break
        return repos
    
    def _extract_languages(self, repos: List[Dict]) -> Dict[str, int]:
        """Extract languages from repositories."""
        languages = {}
        for repo in repos:
            if repo.get('language'):
                lang = repo['language']
                languages[lang] = languages.get(lang, 0) + 1
        return languages
    
    def _extract_frameworks(self, repos: List[Dict]) -> List[str]:
        """Extract frameworks from repository descriptions and topics."""
        frameworks = []
        framework_patterns = {
            'react': ['react', 'next.js', 'gatsby'],
            'django': ['django', 'drf'],
            'vue': ['vue', 'nuxt'],
            'angular': ['angular'],
            'flask': ['flask'],
            'fastapi': ['fastapi'],
            'node': ['node', 'express', 'nestjs'],
            'spring': ['spring', 'springboot'],
            'tensorflow': ['tensorflow', 'keras'],
            'pytorch': ['pytorch'],
        }
        
        for repo in repos:
            repo_name = repo.get('name', '').lower()
            repo_desc = repo.get('description', '').lower()
            topics = repo.get('topics', [])
            
            for framework, patterns in framework_patterns.items():
                for pattern in patterns:
                    if (pattern in repo_name or 
                        pattern in repo_desc or 
                        any(pattern in topic for topic in topics)):
                        if framework not in frameworks:
                            frameworks.append(framework)
        
        return frameworks
    
    def _get_total_commits(self, username: str) -> int:
        """Get total commits from all repos."""
        # Simplified: get contribution count from user's profile
        user_data = self._get_user_data(username)
        if user_data:
            return user_data.get('public_repos', 0) * 10  # Approximation
        return 0
    
    def _analyze_commit_patterns(self, repos: List[Dict]) -> Dict[str, Any]:
        """Analyze commit patterns to determine experience."""
        patterns = {
            'recent_activity': 0,
            'diversity': len(set(repo.get('language') for repo in repos if repo.get('language'))),
            'project_size': 0,
        }
        
        for repo in repos:
            if repo.get('size', 0) > 1000:
                patterns['project_size'] += 1
        
        return patterns
    
    def _determine_skill_levels(self, languages: Dict[str, int], patterns: Dict[str, Any]) -> Dict[str, str]:
        """Determine skill levels based on language usage and patterns."""
        skill_levels = {}
        
        # Determine primary language
        if languages:
            primary_lang = max(languages, key=languages.get)
            
            # Language-specific level determination
            for lang, count in languages.items():
                if lang == primary_lang:
                    if patterns.get('project_size', 0) > 10:
                        skill_levels[lang] = 'expert'
                    elif patterns.get('project_size', 0) > 5:
                        skill_levels[lang] = 'advanced'
                    elif patterns.get('project_size', 0) > 2:
                        skill_levels[lang] = 'intermediate'
                    else:
                        skill_levels[lang] = 'beginner'
                else:
                    if count > 5:
                        skill_levels[lang] = 'intermediate'
                    else:
                        skill_levels[lang] = 'beginner'
        
        return skill_levels
    
    def _get_contributions(self, username: str) -> int:
        """Get contribution count."""
        # Simplified: use public repo count and commits
        user_data = self._get_user_data(username)
        if user_data:
            return user_data.get('public_repos', 0) * 5  # Approximation
        return 0


class SkillDetector:
    """
    Detects skills from user activity and interests.
    """
    
    SKILL_KEYWORDS = {
        'frontend': ['react', 'vue', 'angular', 'html', 'css', 'javascript', 'typescript'],
        'backend': ['python', 'django', 'node', 'express', 'java', 'spring', 'go', 'rust'],
        'devops': ['docker', 'kubernetes', 'aws', 'gcp', 'azure', 'jenkins', 'terraform'],
        'data': ['pandas', 'numpy', 'sql', 'spark', 'hadoop', 'dbt'],
        'ml': ['tensorflow', 'pytorch', 'scikit-learn', 'keras', 'nlp', 'cv'],
        'security': ['owasp', 'penetration', 'crypto', 'auth', 'oauth'],
        'testing': ['pytest', 'jest', 'selenium', 'cypress', 'unit-test'],
        'documentation': ['sphinx', 'mkdocs', 'readthedocs', 'api-docs'],
    }
    
    @classmethod
    def detect_skills(cls, profile_data: Dict[str, Any], user_interests: List[str] = None) -> Dict[str, Any]:
        """
        Detect user skills from GitHub data and interests.
        
        Args:
            profile_data: GitHub profile data
            user_interests: User's stated interests
        
        Returns:
            Dict: Detected skills and categories
        """
        skills = {
            'languages': [],
            'frameworks': [],
            'categories': [],
            'skill_levels': {}
        }
        
        # Extract languages
        languages = profile_data.get('languages', {})
        skill_levels = profile_data.get('skill_levels', {})
        
        for lang, count in languages.items():
            if count > 0:
                skills['languages'].append(lang)
                skills['skill_levels'][lang] = skill_levels.get(lang, 'beginner')
        
        # Extract frameworks
        frameworks = profile_data.get('frameworks', [])
        skills['frameworks'] = frameworks
        
        # Detect categories
        all_skills = list(languages.keys()) + frameworks + (user_interests or [])
        
        detected_categories = set()
        for skill in all_skills:
            for category, keywords in cls.SKILL_KEYWORDS.items():
                if any(keyword in skill.lower() for keyword in keywords):
                    detected_categories.add(category)
        
        skills['categories'] = list(detected_categories)
        
        return skills