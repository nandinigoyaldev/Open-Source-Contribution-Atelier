"""
NLP-based issue skill tagging.
"""

import re
from typing import List, Dict, Any, Set
from apps.skill_matching.models import SkillTag, IssueSkillTag
from apps.ml_triage.models import Issue
import logging

logger = logging.getLogger(__name__)


class SkillTagger:
    """
    Automatically tag issues with required skills.
    """

    # Skill patterns
    SKILL_PATTERNS = {
        "python": ["python", "py", "django", "flask", "fastapi", "pandas", "numpy"],
        "javascript": [
            "javascript",
            "js",
            "node",
            "react",
            "vue",
            "angular",
            "express",
        ],
        "typescript": ["typescript", "ts", "next.js", "nestjs"],
        "java": ["java", "spring", "maven", "gradle"],
        "go": ["go", "golang"],
        "rust": ["rust"],
        "docker": ["docker", "container", "image"],
        "kubernetes": ["kubernetes", "k8s", "helm", "pod"],
        "aws": ["aws", "ec2", "s3", "lambda", "cloudformation"],
        "gcp": ["gcp", "google cloud", "gke", "bigquery"],
        "azure": ["azure", "microsoft cloud"],
        "react": ["react", "reactjs", "next.js", "gatsby"],
        "vue": ["vue", "vuejs", "nuxt"],
        "django": ["django", "drf", "django rest framework"],
        "tensorflow": ["tensorflow", "tf", "keras"],
        "pytorch": ["pytorch", "torch"],
        "sql": ["sql", "postgresql", "mysql", "database", "db"],
        "mongodb": ["mongodb", "mongo"],
        "redis": ["redis"],
        "git": ["git", "github"],
        "testing": ["test", "testing", "pytest", "jest", "unittest"],
        "documentation": ["docs", "documentation", "sphinx", "mkdocs"],
        "api": ["api", "rest", "graphql", "endpoint"],
        "security": ["security", "auth", "oauth", "jwt", "csrf"],
        "devops": ["devops", "ci/cd", "pipeline", "deployment", "infra"],
        "frontend": ["frontend", "ui", "ux", "css", "html", "responsive"],
        "backend": ["backend", "server", "database", "api"],
        "linux": ["linux", "ubuntu", "bash", "shell"],
        "windows": ["windows", "powershell", "cmd"],
        "macos": ["macos", "osx", "apple"],
    }

    def __init__(self):
        self._ensure_skill_tags()

    def _ensure_skill_tags(self):
        """Ensure all skill tags exist in database."""
        for skill_name in self.SKILL_PATTERNS.keys():
            SkillTag.objects.get_or_create(
                name=skill_name, defaults={"category": self._get_category(skill_name)}
            )

    def _get_category(self, skill_name: str) -> str:
        """Get category for a skill."""
        categories = {
            "python": "language",
            "javascript": "language",
            "typescript": "language",
            "java": "language",
            "go": "language",
            "rust": "language",
            "react": "framework",
            "vue": "framework",
            "django": "framework",
            "docker": "tool",
            "kubernetes": "tool",
            "aws": "cloud",
            "tensorflow": "ml",
            "pytorch": "ml",
            "sql": "database",
            "mongodb": "database",
            "redis": "database",
            "git": "version_control",
            "testing": "testing",
            "documentation": "documentation",
            "api": "api",
            "security": "security",
            "devops": "devops",
            "frontend": "domain",
            "backend": "domain",
            "linux": "os",
            "windows": "os",
            "macos": "os",
        }
        return categories.get(skill_name, "other")

    def tag_issue(self, issue: Issue) -> List[IssueSkillTag]:
        """
        Tag an issue with skills.
        """
        text = f"{issue.title} {issue.body}".lower()
        tags = []

        for skill_name, patterns in self.SKILL_PATTERNS.items():
            confidence = 0.0

            for pattern in patterns:
                if pattern in text:
                    confidence += 0.2

            if confidence > 0:
                skill, _ = SkillTag.objects.get_or_create(
                    name=skill_name,
                    defaults={"category": self._get_category(skill_name)},
                )

                # Cap confidence at 1.0
                confidence = min(1.0, confidence)

                tag, created = IssueSkillTag.objects.get_or_create(
                    issue=issue,
                    skill=skill,
                    defaults={"confidence": confidence, "auto_tagged": True},
                )

                if not created:
                    tag.confidence = confidence
                    tag.save()

                tags.append(tag)

        return tags

    def get_required_skills(self, issue: Issue) -> List[Dict[str, Any]]:
        """
        Get required skills for an issue.
        """
        tags = IssueSkillTag.objects.filter(issue=issue).select_related("skill")
        return [
            {
                "skill": tag.skill.name,
                "category": tag.skill.category,
                "confidence": tag.confidence,
            }
            for tag in tags
        ]
