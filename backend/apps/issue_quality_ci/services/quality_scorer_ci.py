"""
NLP-based issue quality scoring for CI/CD pipeline.
"""

import re
import json
from typing import Dict, Any, List, Tuple
from textblob import TextBlob
from apps.issue_quality_ci.models import (
    IssueQualityRecord,
    QualityMetric,
    QualityComment,
)
import logging

logger = logging.getLogger(__name__)


class IssueQualityScorerCI:
    """
    Score issue quality and generate suggestions.
    """

    def score_issue(self, title: str, body: str, issue_number: int) -> Dict[str, Any]:
        """
        Score issue quality and generate suggestions.
        """
        # Calculate individual scores
        clarity = self._score_clarity(title, body)
        scope = self._score_scope(title, body)
        acceptance = self._score_acceptance(body)
        touchpoints = self._score_touchpoints(body)

        # Calculate overall
        overall = clarity * 0.35 + scope * 0.25 + acceptance * 0.25 + touchpoints * 0.15

        # Detect issues
        clarity_issues = self._detect_clarity_issues(title, body)
        scope_issues = self._detect_scope_issues(title, body)
        acceptance_issues = self._detect_acceptance_issues(body)

        # Generate suggestions
        suggestions = self._generate_suggestions(
            clarity,
            scope,
            acceptance,
            touchpoints,
            clarity_issues,
            scope_issues,
            acceptance_issues,
        )

        # Accessibility scoring
        accessibility = self._score_accessibility(body)

        return {
            "clarity_score": clarity * 100,
            "scope_score": scope * 100,
            "acceptance_criteria_score": acceptance * 100,
            "touchpoints_score": touchpoints * 100,
            "overall_quality_score": overall * 100,
            "language_accessibility": accessibility["language"] * 100,
            "inclusivity_score": accessibility["inclusivity"] * 100,
            "clarity_issues": clarity_issues,
            "scope_issues": scope_issues,
            "acceptance_issues": acceptance_issues,
            "suggestions": suggestions,
        }

    def _score_clarity(self, title: str, body: str) -> float:
        """
        Score issue clarity.
        """
        full_text = f"{title} {body}"
        score = 0.0

        # Title clarity
        title_words = len(title.split())
        if title_words > 5:
            score += 0.2

        # Body structure
        if len(body.split()) > 50:
            score += 0.2

        # Sentences are well-formed
        blob = TextBlob(body)
        if blob.sentences:
            avg_length = sum(len(s.sentences) for s in blob.sentences) / len(
                blob.sentences
            )
            if 10 <= avg_length <= 20:
                score += 0.2

        # Grammar check (simplified)
        if self._check_grammar(body):
            score += 0.2

        # No excessive jargon
        if self._check_jargon(body):
            score += 0.2

        return min(1.0, score)

    def _score_scope(self, title: str, body: str) -> float:
        """
        Score issue scope clarity.
        """
        score = 0.0

        # Clear problem statement
        problem_indicators = ["problem", "issue", "bug", "feature", "enhancement"]
        if any(p in body.lower() for p in problem_indicators):
            score += 0.3

        # Scope boundaries
        scope_indicators = ["scope", "affects", "impact", "only", "just"]
        if any(s in body.lower() for s in scope_indicators):
            score += 0.3

        # Limited scope (not too broad)
        if len(body.split()) < 200:
            score += 0.2

        # Clear boundaries
        if "outside" in body.lower() or "not" in body.lower():
            score += 0.2

        return min(1.0, score)

    def _score_acceptance(self, body: str) -> float:
        """
        Score acceptance criteria.
        """
        score = 0.0

        # Has acceptance criteria section
        acceptance_indicators = [
            "acceptance criteria",
            "done",
            "definition of done",
            "criteria",
            "requirements",
            "must",
            "should",
        ]

        if any(a in body.lower() for a in acceptance_indicators):
            score += 0.4

        # Has checkboxes or numbered list
        if "[" in body or "]" in body or re.search(r"\d+\.", body):
            score += 0.3

        # Has measurable outcomes
        measurable_indicators = ["count", "number", "percentage", "time", "seconds"]
        if any(m in body.lower() for m in measurable_indicators):
            score += 0.3

        return min(1.0, score)

    def _score_touchpoints(self, body: str) -> float:
        """
        Score codebase touchpoints.
        """
        score = 0.0

        # Mentions specific files or components
        code_indicators = [
            "file",
            "component",
            "module",
            "function",
            "class",
            ".py",
            ".js",
            ".ts",
            ".css",
            ".html",
        ]
        if any(c in body.lower() for c in code_indicators):
            score += 0.4

        # Mentions specific code
        if "```" in body or "def " in body or "class " in body:
            score += 0.3

        # Has reproduction steps
        if "step" in body.lower() or re.search(r"\d+\.", body):
            score += 0.3

        return min(1.0, score)

    def _detect_clarity_issues(self, title: str, body: str) -> List[str]:
        """
        Detect clarity issues.
        """
        issues = []

        if len(title.split()) < 3:
            issues.append(
                "Title is too short. Please provide a more descriptive title."
            )

        if len(body.split()) < 20:
            issues.append("Description is too brief. Please provide more details.")

        if not self._check_grammar(body):
            issues.append("Grammar issues detected. Please review the description.")

        return issues

    def _detect_scope_issues(self, title: str, body: str) -> List[str]:
        """
        Detect scope issues.
        """
        issues = []

        problem_indicators = ["problem", "issue", "bug", "feature", "enhancement"]
        if not any(p in body.lower() for p in problem_indicators):
            issues.append("Please clarify if this is a bug, feature, or enhancement.")

        if len(body.split()) > 300:
            issues.append("Issue is too broad. Try to narrow down the scope.")

        return issues

    def _detect_acceptance_issues(self, body: str) -> List[str]:
        """
        Detect acceptance criteria issues.
        """
        issues = []

        acceptance_indicators = ["acceptance criteria", "done", "definition of done"]
        if not any(a in body.lower() for a in acceptance_indicators):
            issues.append("Please define acceptance criteria (what does 'done' mean?)")

        if "[" not in body or "]" not in body:
            issues.append("Consider using a checklist for acceptance criteria")

        return issues

    def _generate_suggestions(
        self,
        clarity: float,
        scope: float,
        acceptance: float,
        touchpoints: float,
        clarity_issues: List[str],
        scope_issues: List[str],
        acceptance_issues: List[str],
    ) -> List[str]:
        """
        Generate improvement suggestions.
        """
        suggestions = []

        if clarity < 0.6:
            suggestions.append("✅ Improve clarity: Use clear and concise language")

        if scope < 0.6:
            suggestions.append(
                "✅ Define scope: Be specific about what's included and excluded"
            )

        if acceptance < 0.6:
            suggestions.append(
                "✅ Add acceptance criteria: Define what 'done' looks like"
            )

        if touchpoints < 0.6:
            suggestions.append(
                "✅ Add codebase touchpoints: Mention relevant files or components"
            )

        if clarity_issues:
            suggestions.append(f"✅ {clarity_issues[0]}")

        if scope_issues:
            suggestions.append(f"✅ {scope_issues[0]}")

        return suggestions

    def _check_grammar(self, text: str) -> bool:
        """
        Check grammar (simplified).
        """
        # Check for sentence capitalization
        sentences = text.split(".")
        capitalized = sum(1 for s in sentences if s.strip() and s.strip()[0].isupper())

        return capitalized / max(len(sentences), 1) > 0.5

    def _check_jargon(self, text: str) -> bool:
        """
        Check for excessive jargon (simplified).
        """
        jargon_words = ["utilize", "leverage", "synergy", "optimize", "paradigm"]
        jargon_count = sum(1 for j in jargon_words if j in text.lower())

        return jargon_count < 3

    def _score_accessibility(self, text: str) -> Dict[str, float]:
        """
        Score accessibility of issue.
        """
        language_score = 0.5
        inclusivity_score = 0.5

        # Language accessibility
        if len(text.split()) < 500:
            language_score += 0.3
        if self._check_grammar(text):
            language_score += 0.2

        # Inclusivity
        inclusive_terms = [
            "everyone",
            "all",
            "anyone",
            "people",
            "community",
            "contributor",
            "newcomer",
            "beginner",
        ]
        if any(i in text.lower() for i in inclusive_terms):
            inclusivity_score += 0.3

        # No exclusionary language
        exclusionary_terms = ["only", "just", "expert", "professional"]
        if not any(e in text.lower() for e in exclusionary_terms):
            inclusivity_score += 0.2

        return {
            "language": min(1.0, language_score),
            "inclusivity": min(1.0, inclusivity_score),
        }
