"""
AI-powered recommendation engine for tasks.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from apps.recommendations.models import (
    UserSkillProfile,
    IssueSkillTag,
    TaskRecommendation,
    MentorProfile,
    RecommendationFeedback,
)

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    AI-powered recommendation engine for tasks.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000)

    def generate_recommendations(
        self, user: User, limit: int = 10
    ) -> List[TaskRecommendation]:
        """
        Generate personalized task recommendations for a user.

        Args:
            user: User to generate recommendations for
            limit: Maximum number of recommendations

        Returns:
            List[TaskRecommendation]: Generated recommendations
        """
        # Get user profile
        try:
            profile = UserSkillProfile.objects.get(user=user)
        except UserSkillProfile.DoesNotExist:
            logger.warning(f"No skill profile for user {user.username}")
            return []

        # Get all tagged issues
        tagged_issues = IssueSkillTag.objects.all()

        if not tagged_issues:
            logger.info("No tagged issues available")
            return []

        # Calculate scores for each issue
        recommendations = []
        for issue_tag in tagged_issues:
            score = self._calculate_recommendation_score(profile, issue_tag)

            if score > 30:  # Threshold for good recommendation
                # Check if already recommended
                existing = TaskRecommendation.objects.filter(
                    user=user,
                    content_type=issue_tag.content_type,
                    object_id=issue_tag.object_id,
                    status__in=["pending", "accepted"],
                ).first()

                if existing:
                    # Update existing recommendation
                    existing.recommendation_score = score
                    existing.save()
                    recommendations.append(existing)
                else:
                    # Create new recommendation
                    recommendation = TaskRecommendation.objects.create(
                        user=user,
                        content_type=issue_tag.content_type,
                        object_id=issue_tag.object_id,
                        recommendation_score=score,
                        skill_match_score=self._calculate_skill_match(
                            profile, issue_tag
                        ),
                        interest_match_score=self._calculate_interest_match(
                            profile, issue_tag
                        ),
                        matched_skills=self._get_matched_skills(profile, issue_tag),
                        missing_skills=self._get_missing_skills(profile, issue_tag),
                        suggested_mentors=self._suggest_mentors(issue_tag),
                        reasoning=self._generate_reasoning(profile, issue_tag),
                    )
                    recommendations.append(recommendation)

        # Sort by score and limit
        recommendations.sort(key=lambda x: x.recommendation_score, reverse=True)
        return recommendations[:limit]

    def _calculate_recommendation_score(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> float:
        """
        Calculate overall recommendation score (0-100).
        """
        skill_match = self._calculate_skill_match(profile, issue_tag)
        interest_match = self._calculate_interest_match(profile, issue_tag)
        difficulty_match = self._calculate_difficulty_match(profile, issue_tag)

        # Weighted combination
        score = skill_match * 0.5 + interest_match * 0.3 + difficulty_match * 0.2

        return min(score, 100.0)

    def _calculate_skill_match(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> float:
        """
        Calculate skill match score (0-100).
        """
        if not issue_tag.required_skills:
            return 50.0  # Neutral if no skills specified

        user_skills = set(
            profile.primary_languages
            + profile.frameworks
            + [
                k
                for k, v in profile.skill_levels.items()
                if v in ["advanced", "expert"]
            ]
        )
        required_skills = set(issue_tag.required_skills)

        if not user_skills:
            return 0.0

        matched = user_skills.intersection(required_skills)
        match_percentage = (len(matched) / len(required_skills)) * 100

        return min(match_percentage, 100.0)

    def _calculate_interest_match(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> float:
        """
        Calculate interest match score (0-100).
        """
        if not profile.interests:
            return 50.0

        user_interests = set(profile.interests)
        issue_categories = set(issue_tag.categories)

        if not issue_categories:
            return 50.0

        matched = user_interests.intersection(issue_categories)
        match_percentage = (len(matched) / len(issue_categories)) * 100

        return min(match_percentage, 100.0)

    def _calculate_difficulty_match(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> float:
        """
        Calculate difficulty match score (0-100).
        """
        # Map difficulty to score
        difficulty_map = {
            "beginner": 20,
            "intermediate": 50,
            "advanced": 80,
            "expert": 100,
        }

        # Get user's max skill level
        user_max_level = "beginner"
        for skill, level in profile.skill_levels.items():
            if difficulty_map.get(level, 0) > difficulty_map.get(user_max_level, 0):
                user_max_level = level

        issue_difficulty = issue_tag.difficulty

        # Compare levels
        user_score = difficulty_map.get(user_max_level, 20)
        issue_score = difficulty_map.get(issue_difficulty, 20)

        if user_score >= issue_score:
            return 80.0  # User is capable
        else:
            return max(0, 100 - (issue_score - user_score) * 2)

    def _get_matched_skills(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> List[str]:
        """Get skills that match between user and issue."""
        user_skills = set(profile.primary_languages + profile.frameworks)
        required_skills = set(issue_tag.required_skills)
        return list(user_skills.intersection(required_skills))

    def _get_missing_skills(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> List[str]:
        """Get skills that are missing for the issue."""
        user_skills = set(profile.primary_languages + profile.frameworks)
        required_skills = set(issue_tag.required_skills)
        return list(required_skills - user_skills)

    def _suggest_mentors(self, issue_tag: IssueSkillTag) -> List[Dict]:
        """Suggest mentors for this issue."""
        mentors = MentorProfile.objects.filter(
            is_active=True, skills__overlap=issue_tag.required_skills
        ).order_by("-rating")[:3]

        return [
            {
                "id": mentor.user.id,
                "username": mentor.user.username,
                "skills": mentor.skills,
                "rating": mentor.rating,
            }
            for mentor in mentors
        ]

    def _generate_reasoning(
        self, profile: UserSkillProfile, issue_tag: IssueSkillTag
    ) -> str:
        """Generate reasoning for recommendation."""
        matched = self._get_matched_skills(profile, issue_tag)
        missing = self._get_missing_skills(profile, issue_tag)

        reasoning_parts = []

        if matched:
            reasoning_parts.append(
                f"Your skills in {', '.join(matched)} match this task"
            )

        if missing:
            reasoning_parts.append(
                f"You'll learn {', '.join(missing)} while working on this"
            )

        if issue_tag.difficulty == "beginner":
            reasoning_parts.append("This is a beginner-friendly task")

        if not reasoning_parts:
            reasoning_parts.append("This task seems like a good fit for you")

        return ". ".join(reasoning_parts) + "."


class AutoTagger:
    """
    Automatic issue tagging using NLP.
    """

    SKILL_PATTERNS = {
        "javascript": [
            "javascript",
            "js",
            "react",
            "vue",
            "angular",
            "node",
            "express",
        ],
        "python": ["python", "django", "flask", "fastapi", "pandas", "numpy", "pytest"],
        "java": ["java", "spring", "maven", "gradle"],
        "go": ["go", "golang"],
        "rust": ["rust"],
        "docker": ["docker", "container", "image"],
        "kubernetes": ["kubernetes", "k8s", "helm", "pod"],
        "aws": ["aws", "ec2", "s3", "lambda", "cloudformation"],
        "gcp": ["gcp", "google cloud", "cloud run", "bigquery"],
        "azure": ["azure", "microsoft cloud"],
        "react": ["react", "reactjs", "next.js", "gatsby"],
        "vue": ["vue", "vuejs", "nuxt"],
        "django": ["django", "drf", "django rest framework"],
        "tensorflow": ["tensorflow", "tf", "keras"],
        "pytorch": ["pytorch", "torch"],
        "sql": ["sql", "postgresql", "mysql", "db", "database"],
        "testing": ["test", "pytest", "jest", "unittest", "integration"],
        "documentation": ["docs", "documentation", "sphinx", "mkdocs"],
    }

    DIFFICULTY_KEYWORDS = {
        "beginner": ["good first issue", "beginner", "easy", "simple", "minor"],
        "intermediate": ["medium", "moderate", "some experience"],
        "advanced": ["hard", "complex", "advanced", "expert"],
    }

    @classmethod
    def tag_issue(cls, title: str, description: str, body: str = "") -> Dict[str, Any]:
        """
        Automatically tag an issue with skills and difficulty.

        Args:
            title: Issue title
            description: Issue description
            body: Issue body text

        Returns:
            Dict: Tags with confidence scores
        """
        text = f"{title} {description} {body}".lower()

        # Detect skills
        detected_skills = set()
        skill_confidence = {}

        for skill, patterns in cls.SKILL_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    detected_skills.add(skill)
                    if skill not in skill_confidence:
                        skill_confidence[skill] = 0
                    skill_confidence[skill] += 1

        # Normalize confidence
        max_confidence = max(skill_confidence.values()) if skill_confidence else 1
        for skill in skill_confidence:
            skill_confidence[skill] = (skill_confidence[skill] / max_confidence) * 100

        # Detect difficulty
        difficulty = "intermediate"
        difficulty_confidence = 50

        for level, keywords in cls.DIFFICULTY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    difficulty = level
                    difficulty_confidence = 80
                    break

        # Detect categories
        categories = set()
        for skill in detected_skills:
            for category, keywords in cls.SKILL_PATTERNS.items():
                if skill in keywords:
                    categories.add(category)

        return {
            "required_skills": list(detected_skills),
            "categories": list(categories),
            "difficulty": difficulty,
            "skill_confidence": skill_confidence,
            "difficulty_confidence": difficulty_confidence,
            "auto_tagged": True,
        }
