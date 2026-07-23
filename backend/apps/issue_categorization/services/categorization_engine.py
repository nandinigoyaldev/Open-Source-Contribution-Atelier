"""
ML-based categorization engine for issues.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.naive_bayes import MultinomialNB
import numpy as np
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from apps.issue_categorization.models import (
    Category,
    IssueTag,
    IssueCategoryAssignment,
    IssueTagAssignment,
    CategorySuggestion,
)

logger = logging.getLogger(__name__)


class CategorizationEngine:
    """
    ML-powered categorization engine for issues.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000, stop_words="english", ngram_range=(1, 2)
        )
        self.classifier = MultinomialNB()
        self._is_trained = False

    def train(self, documents: List[Dict]):
        """
        Train the categorization model.

        Args:
            documents: List of dicts with 'text' and 'category_id'
        """
        if not documents:
            return

        texts = [doc["text"] for doc in documents]
        labels = [doc["category_id"] for doc in documents]

        X = self.vectorizer.fit_transform(texts)
        self.classifier.fit(X, labels)
        self._is_trained = True

        logger.info(f"Model trained on {len(documents)} documents")

    def categorize_issue(
        self, title: str, description: str, body: str = ""
    ) -> Dict[str, Any]:
        """
        Categorize an issue.

        Args:
            title: Issue title
            description: Issue description
            body: Issue body text

        Returns:
            Dict: Categorization results
        """
        text = f"{title} {description} {body}"

        # Get category suggestions
        categories = self._suggest_categories(text)
        tags = self._suggest_tags(text)

        return {
            "categories": categories,
            "tags": tags,
            "confidence": {
                "categories": (
                    sum(c["score"] for c in categories) / len(categories)
                    if categories
                    else 0
                ),
                "tags": sum(t["score"] for t in tags) / len(tags) if tags else 0,
            },
        }

    def _suggest_categories(self, text: str) -> List[Dict]:
        """
        Suggest categories using ML.
        """
        if not self._is_trained:
            return self._keyword_based_categories(text)

        # Get all categories
        categories = Category.objects.all()
        if not categories:
            return []

        # Create feature vector
        text_vector = self.vectorizer.transform([text])

        # Predict category
        predictions = self.classifier.predict_proba(text_vector)[0]

        # Get top categories
        results = []
        for idx, prob in enumerate(predictions):
            if prob > 0.1:  # Threshold
                results.append(
                    {
                        "id": categories[idx].id,
                        "name": categories[idx].name,
                        "score": prob,
                        "path": categories[idx].get_full_path(),
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:5]

    def _keyword_based_categories(self, text: str) -> List[Dict]:
        """
        Fallback: keyword-based category suggestion.
        """
        categories = Category.objects.all()
        results = []

        text_lower = text.lower()

        for category in categories:
            # Check if category name appears in text
            if category.name.lower() in text_lower:
                results.append(
                    {
                        "id": category.id,
                        "name": category.name,
                        "score": 0.7,
                        "path": category.get_full_path(),
                        "matched": True,
                    }
                )
            else:
                # Check child categories
                for child in category.get_descendants():
                    if child.name.lower() in text_lower:
                        results.append(
                            {
                                "id": child.id,
                                "name": child.name,
                                "score": 0.6,
                                "path": child.get_full_path(),
                                "matched": True,
                            }
                        )
                        break

        return results[:5]

    def _suggest_tags(self, text: str) -> List[Dict]:
        """
        Suggest tags using pattern matching.
        """
        # Predefined tag patterns
        tag_patterns = {
            "javascript": ["javascript", "js", "react", "vue", "angular", "node"],
            "python": ["python", "django", "flask", "fastapi", "pandas"],
            "java": ["java", "spring", "maven"],
            "go": ["go", "golang"],
            "docker": ["docker", "container", "k8s", "kubernetes"],
            "aws": ["aws", "ec2", "s3", "lambda"],
            "gcp": ["gcp", "google", "cloud", "gke"],
            "azure": ["azure", "microsoft", "azuredevops"],
            "database": ["sql", "postgresql", "mysql", "mongodb", "redis"],
            "frontend": ["ui", "ux", "frontend", "react", "vue", "css", "html"],
            "backend": ["backend", "api", "rest", "graphql", "server"],
            "devops": ["devops", "ci/cd", "pipeline", "deployment", "infra"],
            "security": ["security", "auth", "oauth", "jwt", "csrf", "xss"],
            "testing": ["test", "testing", "pytest", "jest", "unittest"],
            "documentation": ["docs", "documentation", "readme", "tutorial"],
        }

        text_lower = text.lower()
        suggested_tags = []

        for tag_name, patterns in tag_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    # Get or create tag
                    tag, created = IssueTag.objects.get_or_create(
                        name=tag_name, defaults={"slug": tag_name, "tag_type": "auto"}
                    )
                    if created:
                        logger.info(f"Created new tag: {tag_name}")

                    suggested_tags.append(
                        {
                            "id": tag.id,
                            "name": tag.name,
                            "score": 0.7 if tag_name in text_lower else 0.5,
                        }
                    )
                    break

        return suggested_tags[:10]

    def auto_categorize_issue(
        self, issue, title: str, description: str, body: str = ""
    ):
        """
        Auto-categorize an issue and create suggestions.

        Args:
            issue: Issue instance
            title: Issue title
            description: Issue description
            body: Issue body text

        Returns:
            CategorySuggestion: The created suggestion
        """
        # Get suggestions
        results = self.categorize_issue(title, description, body)

        # Create suggestion
        content_type = ContentType.objects.get_for_model(issue)

        suggestion = CategorySuggestion.objects.create(
            issue_content_type=content_type,
            issue_object_id=issue.id,
            suggested_categories=[
                {"id": c["id"], "score": c["score"]} for c in results["categories"][:5]
            ],
            suggested_tags=[
                {"id": t["id"], "score": t["score"]} for t in results["tags"][:10]
            ],
            confidence_scores=results["confidence"],
        )

        return suggestion


class SearchEngine:
    """
    Advanced search for hierarchical categories.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=500)

    def search(
        self, query: str, category_id: Optional[int] = None, **filters
    ) -> List[Dict]:
        """
        Search issues with category filtering.

        Args:
            query: Search query
            category_id: Optional category filter
            **filters: Additional filters (difficulty, tags, etc.)

        Returns:
            List[Dict]: Search results
        """
        # Base queryset
        base_qs = IssueCategoryAssignment.objects.all()

        # Apply category filter
        if category_id:
            base_qs = base_qs.filter(category_id=category_id)

        # Apply filters
        # (Implementation depends on how issues are stored)

        # Calculate relevance
        results = []
        for assignment in base_qs:
            issue = assignment.issue
            if not issue:
                continue

            score = self._calculate_relevance(query, issue)
            if score > 0.1:
                results.append(
                    {
                        "issue": issue,
                        "category": assignment.category,
                        "score": score,
                        "path": assignment.category.get_full_path(),
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _calculate_relevance(self, query: str, issue) -> float:
        """
        Calculate relevance score for an issue.
        """
        # Combine issue text
        text = f"{issue.title} {issue.description}"

        # Simple keyword matching
        query_words = query.lower().split()
        text_lower = text.lower()

        matches = sum(1 for word in query_words if word in text_lower)
        return matches / len(query_words) if query_words else 0


class HierarchicalNavigator:
    """
    Visual navigation for hierarchical categories.
    """

    def get_tree(self, root_id: Optional[int] = None) -> List[Dict]:
        """
        Get category tree for visual navigation.

        Args:
            root_id: Optional root category ID

        Returns:
            List[Dict]: Category tree
        """
        if root_id:
            root = Category.objects.get(id=root_id)
            return self._build_tree(root)
        else:
            roots = Category.objects.filter(parent=None)
            return [self._build_tree(root) for root in roots]

    def _build_tree(self, category: Category) -> Dict:
        """
        Build tree for a category.
        """
        children = category.children.all()

        return {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "level": category.get_level(),
            "issue_count": category.issue_count,
            "children": [self._build_tree(child) for child in children],
            "has_children": children.exists(),
        }

    def get_path(self, category_id: int) -> List[Dict]:
        """
        Get full path for a category.

        Args:
            category_id: Category ID

        Returns:
            List[Dict]: Category path
        """
        category = Category.objects.get(id=category_id)
        ancestors = category.get_ancestors(include_self=True)

        return [
            {
                "id": ancestor.id,
                "name": ancestor.name,
                "slug": ancestor.slug,
                "level": ancestor.get_level(),
            }
            for ancestor in ancestors
        ]

    def get_issues_by_path(self, category_id: int) -> List[Dict]:
        """
        Get all issues in a category and its subcategories.

        Args:
            category_id: Category ID

        Returns:
            List[Dict]: Issues with their full path
        """
        category = Category.objects.get(id=category_id)

        # Get all descendants
        descendants = category.get_descendants(include_self=True)

        # Get issues for all categories
        assignments = IssueCategoryAssignment.objects.filter(
            category__in=descendants
        ).select_related("category")

        issues = []
        for assignment in assignments:
            issue = assignment.issue
            if issue:
                issues.append(
                    {
                        "issue": issue,
                        "category": assignment.category,
                        "path": assignment.category.get_full_path(),
                    }
                )

        return issues
