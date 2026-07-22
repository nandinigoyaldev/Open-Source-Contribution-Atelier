"""
Quality scoring for issues to prevent WONTFIX labeling.
"""

import re
import hashlib
from typing import Dict, Any, List, Tuple, Optional
from textblob import TextBlob
from langdetect import detect, DetectorFactory

try:
    from googletrans import Translator
except ImportError:
    Translator = None

import numpy as np
from django.core.cache import cache
from apps.issue_quality.models import IssueQualityCheck, DuplicateIssue, WontfixPattern
import logging

logger = logging.getLogger(__name__)

# Set seed for consistent language detection
DetectorFactory.seed = 0


class QualityScorer:
    """
    Score issue quality and detect potential WONTFIX reasons.
    """

    def __init__(self):
        self.translator = Translator() if Translator else None
        self.wontfix_patterns = self._load_wontfix_patterns()

    def analyze_issue(self, title: str, body: str, author: str) -> Dict[str, Any]:
        """
        Comprehensive issue quality analysis.
        """
        full_text = f"{title} {body}"

        # 1. Quality scoring
        quality_scores = self._score_quality(title, body)

        # 2. Language detection
        language_info = self._detect_language(full_text)

        # 3. Duplicate detection
        duplicate_info = self._detect_duplicate(title, body)

        # 4. Environment warnings
        environment_info = self._check_environment(body)

        # 5. Engagement prediction
        engagement_info = self._predict_engagement(title, body)

        # 6. WONTFIX risk assessment
        wontfix_info = self._assess_wontfix_risk(
            title, body, quality_scores, duplicate_info, environment_info
        )

        # 7. Generate recommendations
        recommendations = self._generate_recommendations(
            quality_scores, duplicate_info, environment_info, wontfix_info
        )

        return {
            "quality_score": quality_scores["overall"],
            "clarity_score": quality_scores["clarity"],
            "completeness_score": quality_scores["completeness"],
            "reproducibility_score": quality_scores["reproducibility"],
            "language": language_info["language"],
            "is_english": language_info["is_english"],
            "translation_suggestion": language_info["translation"],
            "is_duplicate": duplicate_info["is_duplicate"],
            "duplicate_confidence": duplicate_info["confidence"],
            "duplicate_of": duplicate_info["duplicate_of"],
            "is_user_specific": environment_info["is_user_specific"],
            "environment_warning": environment_info["warning"],
            "predicted_comments": engagement_info["predicted_comments"],
            "predicted_engagement_score": engagement_info["score"],
            "wontfix_risk_score": wontfix_info["risk_score"],
            "wontfix_reasons": wontfix_info["reasons"],
            "recommendations": recommendations,
        }

    def _score_quality(self, title: str, body: str) -> Dict[str, float]:
        """
        Score issue quality across multiple dimensions.
        """
        full_text = f"{title} {body}"

        # Clarity score: proper grammar, clear language
        clarity_score = self._calculate_clarity(full_text)

        # Completeness score: sufficient detail
        completeness_score = self._calculate_completeness(title, body)

        # Reproducibility score: steps to reproduce
        reproducibility_score = self._calculate_reproducibility(body)

        # Overall score
        overall = (
            clarity_score * 0.4 + completeness_score * 0.4 + reproducibility_score * 0.2
        ) * 100

        return {
            "clarity": clarity_score * 100,
            "completeness": completeness_score * 100,
            "reproducibility": reproducibility_score * 100,
            "overall": overall,
        }

    def _calculate_clarity(self, text: str) -> float:
        """
        Calculate clarity score using NLP.
        """
        try:
            blob = TextBlob(text)

            # Check sentence count and average length
            sentences = blob.sentences
            if not sentences:
                return 0.0

            avg_sentence_length = sum(len(s.sentences) for s in sentences) / len(
                sentences
            )

            # Ideal sentence length: 15-20 words
            clarity = 1 - min(abs(avg_sentence_length - 17) / 17, 0.5)

            # Penalize for spelling errors
            spelling_errors = len(blob.words) - len(
                [w for w in blob.words if w.spellcheck()]
            )
            spelling_ratio = spelling_errors / (len(blob.words) + 1)
            clarity = clarity * (1 - min(spelling_ratio, 0.3))

            return max(0, min(1, clarity))
        except:
            return 0.5

    def _calculate_completeness(self, title: str, body: str) -> float:
        """
        Calculate completeness score.
        """
        score = 0.0

        # Check if title is descriptive (more than 5 words)
        if len(title.split()) > 5:
            score += 0.2

        # Check if body has content
        if len(body.split()) > 20:
            score += 0.3

        # Check for specific sections
        patterns = [
            (r"steps? to reproduce", 0.15),
            (r"expected behavior", 0.15),
            (r"actual behavior", 0.15),
            (r"version|environment", 0.05),
        ]

        lower_body = body.lower()
        for pattern, weight in patterns:
            if re.search(pattern, lower_body):
                score += weight

        return min(1.0, score)

    def _calculate_reproducibility(self, body: str) -> float:
        """
        Calculate reproducibility score.
        """
        score = 0.0

        # Check for code blocks
        if "```" in body:
            score += 0.4

        # Check for step-by-step instructions
        step_patterns = [r"\d+\.\s+", r"step\s+\d+", r"first|second|third|then|finally"]

        for pattern in step_patterns:
            if re.search(pattern, body.lower()):
                score += 0.15

        # Check for actual code snippets
        code_keywords = ["def ", "class ", "function ", "var ", "const ", "let "]
        for keyword in code_keywords:
            if keyword in body:
                score += 0.1

        return min(1.0, score)

    def _detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect language and provide translation if needed.
        """
        try:
            language = detect(text)
            is_english = language == "en"

            result = {"language": language, "is_english": is_english, "translation": ""}

            if not is_english:
                try:
                    translation = self.translator.translate(text, dest="en")
                    result["translation"] = translation.text
                except:
                    result["translation"] = ""

            return result
        except:
            return {"language": "unknown", "is_english": True, "translation": ""}

    def _detect_duplicate(self, title: str, body: str) -> Dict[str, Any]:
        """
        Detect duplicate issues using NLP similarity.
        """
        full_text = f"{title} {body}"
        text_hash = hashlib.md5(full_text.encode()).hexdigest()

        # Check cache
        cache_key = f"duplicate_check_{text_hash}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Compare with existing duplicates
        duplicates = DuplicateIssue.objects.all()
        if not duplicates:
            return {"is_duplicate": False, "confidence": 0.0, "duplicate_of": ""}

        # Simple similarity check (in production, use sentence embeddings)
        max_similarity = 0.0
        similar_issue = ""

        for dup in duplicates[:10]:  # Limit for performance
            dup_text = f"{dup.title} {dup.body}"
            similarity = self._calculate_similarity(full_text, dup_text)
            if similarity > max_similarity:
                max_similarity = similarity
                similar_issue = dup.issue_id

        result = {
            "is_duplicate": max_similarity > 0.7,
            "confidence": max_similarity,
            "duplicate_of": similar_issue if max_similarity > 0.7 else "",
        }

        cache.set(cache_key, result, timeout=3600)  # Cache for 1 hour
        return result

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using simple TF-IDF approach.
        """
        # Simple word overlap for performance
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))

        return overlap / total if total > 0 else 0.0

    def _check_environment(self, body: str) -> Dict[str, Any]:
        """
        Check if issue is environment-specific.
        """
        lower_body = body.lower()

        env_keywords = [
            "my environment",
            "my system",
            "my setup",
            "windows",
            "macos",
            "linux",
            "ubuntu",
            "node version",
            "python version",
            "dependency",
            "local",
            "installation",
            "configuration",
        ]

        is_user_specific = any(keyword in lower_body for keyword in env_keywords)

        return {
            "is_user_specific": is_user_specific,
            "warning": (
                "This appears to be environment-specific. Please provide detailed environment setup."
                if is_user_specific
                else ""
            ),
        }

    def _predict_engagement(self, title: str, body: str) -> Dict[str, Any]:
        """
        Predict engagement (comments, discussion).
        """
        full_text = f"{title} {body}"

        # Factors that drive engagement
        factors = {
            "has_question": any(q in full_text for q in ["?", "how", "why", "what"]),
            "length": len(full_text.split()),
            "has_code": "```" in body
            or any(kw in body for kw in ["def ", "class ", "function "]),
            "clarity": self._calculate_clarity(full_text),
            "title_length": len(title.split()),
        }

        # Simple scoring model
        base_score = 0.3
        if factors["has_question"]:
            base_score += 0.2
        if factors["length"] > 50:
            base_score += 0.15
        if factors["has_code"]:
            base_score += 0.15
        if factors["clarity"] > 0.6:
            base_score += 0.2

        predicted_comments = int(base_score * 10)  # 0-10 comments

        return {"score": base_score * 100, "predicted_comments": predicted_comments}

    def _assess_wontfix_risk(
        self,
        title: str,
        body: str,
        quality_scores: Dict,
        duplicate_info: Dict,
        environment_info: Dict,
    ) -> Dict[str, Any]:
        """
        Assess WONTFIX risk and identify reasons.
        """
        risk_score = 0.0
        reasons = []

        # Quality score risk
        if quality_scores["overall"] < 50:
            risk_score += 30
            reasons.append("Low quality issue (incomplete description)")

        # Duplicate risk
        if duplicate_info["is_duplicate"]:
            risk_score += 25
            reasons.append("Duplicate of existing issue")

        # Environment-specific risk
        if environment_info["is_user_specific"]:
            risk_score += 20
            reasons.append("Environment-specific issue (likely user error)")

        # Language risk (non-English)
        if not self._detect_language(body)["is_english"]:
            risk_score += 15
            reasons.append("Non-English issue (communication barrier)")

        # Check WONTFIX patterns
        for pattern in self.wontfix_patterns:
            if pattern.pattern in body.lower() or pattern.pattern in title.lower():
                risk_score += 10
                reasons.append(pattern.category)

        return {
            "risk_score": min(100, risk_score),
            "reasons": reasons[:5],  # Max 5 reasons
        }

    def _generate_recommendations(
        self,
        quality_scores: Dict,
        duplicate_info: Dict,
        environment_info: Dict,
        wontfix_info: Dict,
    ) -> List[str]:
        """
        Generate actionable recommendations.
        """
        recommendations = []

        if quality_scores["clarity"] < 60:
            recommendations.append("Improve clarity: Use clear and concise language")

        if quality_scores["completeness"] < 60:
            recommendations.append(
                "Add more details: Include steps to reproduce, expected/actual behavior"
            )

        if quality_scores["reproducibility"] < 60:
            recommendations.append("Add code snippets or step-by-step instructions")

        if duplicate_info["is_duplicate"]:
            recommendations.append(
                f'Please check existing issue: {duplicate_info["duplicate_of"]}'
            )

        if environment_info["is_user_specific"]:
            recommendations.append(
                "Include your environment details (OS, versions, dependencies)"
            )

        if not recommendations:
            recommendations.append("Your issue looks good! Quality score is high.")

        return recommendations

    def _load_wontfix_patterns(self) -> List[WontfixPattern]:
        """
        Load WONTFIX patterns from database.
        """
        return list(WontfixPattern.objects.all())
