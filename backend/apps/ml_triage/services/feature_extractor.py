"""
Feature extraction for ML models.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from django.utils import timezone
from apps.ml_triage.models import Issue, Comment, Reaction


class FeatureExtractor:
    """
    Extract features from GitHub issues for ML training.
    """

    def extract_features(self, issue: Issue) -> Dict[str, Any]:
        """
        Extract features from an issue.
        """
        features = {
            # Text features
            'title_length': len(issue.title),
            'body_length': len(issue.body),
            'title_word_count': len(issue.title.split()),
            'body_word_count': len(issue.body.split()),
            'has_code_block': '```' in issue.body,
            'has_link': 'http' in issue.body or 'https' in issue.body,
            
            # Metadata features
            'comments_count': self._get_comment_count(issue),
            'reactions_count': self._get_reaction_count(issue),
            'label_count': self._get_label_count(issue),
            'assignee_count': len(issue.assignees),
            
            # Time features
            'hour_created': issue.created_at.hour,
            'day_of_week': issue.created_at.weekday(),
            'age_days': (timezone.now() - issue.created_at).days,
            
            # Author features
            'author_has_contributions': self._author_has_contributions(issue.author),
            'author_reputation': self._get_author_reputation(issue.author),
            
            # Repository features
            'repo_stars': self._get_repo_stars(issue.repository),
            'repo_contributors': self._get_repo_contributors(issue.repository),
        }
        
        return features

    def _get_comment_count(self, issue: Issue) -> int:
        """Get number of comments on issue."""
        return Comment.objects.filter(issue=issue).count()

    def _get_reaction_count(self, issue: Issue) -> int:
        """Get number of reactions on issue."""
        return Reaction.objects.filter(issue=issue).count()

    def _get_label_count(self, issue: Issue) -> int:
        """Get number of labels on issue."""
        return issue.label_count

    def _author_has_contributions(self, author: str) -> bool:
        """Check if author has contributed before."""
        # Simplified: check if author has previous issues
        return Issue.objects.filter(author=author).count() > 0

    def _get_author_reputation(self, author: str) -> float:
        """Calculate author reputation."""
        issues = Issue.objects.filter(author=author)
        if not issues:
            return 0.0
        
        # Reputation based on number of issues and comments
        comment_count = Comment.objects.filter(author=author).count()
        return (issues.count() * 0.5 + comment_count * 0.1)

    def _get_repo_stars(self, repository: str) -> int:
        """Get repository stars (simplified)."""
        # In production, fetch from GitHub API
        return 100  # Placeholder

    def _get_repo_contributors(self, repository: str) -> int:
        """Get repository contributors (simplified)."""
        # In production, fetch from GitHub API
        return 10  # Placeholder