"""
GitHub API collector for issue metadata.
"""

import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from django.conf import settings
from apps.ml_triage.models import Issue, Comment, Reaction
import logging

logger = logging.getLogger(__name__)


class GitHubCollector:
    """
    Collect issue metadata from GitHub API.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or getattr(settings, 'GITHUB_TOKEN', None)
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'

    def collect_issues(self, repo: str, state: str = 'all', limit: int = 100) -> List[Dict]:
        """
        Collect issues from a GitHub repository.
        """
        issues = []
        page = 1
        
        while len(issues) < limit:
            url = f"{self.base_url}/repos/{repo}/issues"
            params = {
                'state': state,
                'page': page,
                'per_page': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch issues: {response.status_code}")
                break
            
            data = response.json()
            if not data:
                break
            
            for item in data:
                if 'pull_request' not in item:  # Skip pull requests
                    issues.append(item)
                    if len(issues) >= limit:
                        break
            
            page += 1
            time.sleep(1)  # Rate limiting
        
        logger.info(f"Collected {len(issues)} issues from {repo}")
        return issues

    def process_issues(self, repo: str, limit: int = 100):
        """
        Process issues and store in database.
        """
        issues_data = self.collect_issues(repo, limit=limit)
        
        for data in issues_data:
            issue = self._create_or_update_issue(data)
            self._process_comments(issue, data.get('comments_url'))
            self._process_reactions(issue, data.get('reactions', {}))
        
        logger.info(f"Processed {len(issues_data)} issues from {repo}")

    def _create_or_update_issue(self, data: Dict) -> Issue:
        """
        Create or update issue in database.
        """
        github_id = data['id']
        
        issue, created = Issue.objects.update_or_create(
            github_id=github_id,
            defaults={
                'repository': data['repository']['full_name'],
                'number': data['number'],
                'title': data['title'],
                'body': data['body'] or '',
                'state': data['state'],
                'author': data['user']['login'],
                'assignees': [a['login'] for a in data.get('assignees', [])],
                'created_at': datetime.strptime(data['created_at'], '%Y-%m-%dT%H:%M:%SZ'),
                'updated_at': datetime.strptime(data['updated_at'], '%Y-%m-%dT%H:%M:%SZ'),
                'closed_at': datetime.strptime(data['closed_at'], '%Y-%m-%dT%H:%M:%SZ') if data.get('closed_at') else None,
                'label_count': len(data.get('labels', [])),
            }
        )
        
        return issue

    def _process_comments(self, issue: Issue, comments_url: str):
        """
        Process comments for an issue.
        """
        if not comments_url:
            return
        
        response = requests.get(comments_url, headers=self.headers)
        if response.status_code != 200:
            return
        
        for data in response.json():
            Comment.objects.get_or_create(
                issue=issue,
                author=data['user']['login'],
                created_at=datetime.strptime(data['created_at'], '%Y-%m-%dT%H:%M:%SZ'),
                defaults={'body': data['body']}
            )

    def _process_reactions(self, issue: Issue, reactions_data: Dict):
        """
        Process reactions for an issue.
        """
        if not reactions_data:
            return
        
        # Simplified reaction processing
        for reaction_type, count in reactions_data.items():
            if isinstance(count, int) and count > 0:
                for i in range(count):
                    Reaction.objects.get_or_create(
                        issue=issue,
                        user='unknown',
                        reaction_type=reaction_type,
                        created_at=issue.created_at
                    )