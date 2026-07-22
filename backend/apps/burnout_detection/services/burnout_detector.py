"""
ML-based burnout detection system.
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, Tuple
from django.core.cache import cache
from apps.burnout_detection.models import ContributorActivity, BurnoutSignal
import logging

logger = logging.getLogger(__name__)


class BurnoutDetector:
    """
    Detect burnout signals in contributors.
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.thresholds = {
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "critical": 0.9,
        }

    def detect_burnout(self, activity: ContributorActivity) -> Dict[str, Any]:
        """
        Detect burnout in a contributor.
        """
        # Calculate burnout score
        score = self._calculate_burnout_score(activity)
        risk_level = self._determine_risk_level(score)

        # Detect specific signals
        signals = self._detect_signals(activity)

        # Update activity record
        activity.burnout_score = score * 100
        activity.burnout_risk = risk_level
        activity.save()

        return {
            "score": score * 100,
            "risk_level": risk_level,
            "signals": signals,
            "needs_intervention": risk_level in ["high", "critical"],
        }

    def _calculate_burnout_score(self, activity: ContributorActivity) -> float:
        """
        Calculate burnout score (0-1).
        """
        score = 0.0
        factors = []

        # Activity decline factor
        if activity.activity_trend < -0.3:
            score += 0.25
            factors.append("declining_activity")

        # Review decline factor
        if activity.review_trend < -0.3:
            score += 0.2
            factors.append("declining_reviews")

        # Response time factor
        if activity.avg_response_time > 48:  # 48+ hours
            score += 0.2
            factors.append("slow_response")

        # Sentiment factor
        if activity.sentiment_score < -0.2:
            score += 0.2
            factors.append("negative_sentiment")

        # Sentiment trend factor
        if activity.sentiment_trend < -0.1:
            score += 0.15
            factors.append("declining_sentiment")

        return min(1.0, score)

    def _determine_risk_level(self, score: float) -> str:
        """
        Determine risk level from score.
        """
        if score >= 0.9:
            return "critical"
        elif score >= 0.7:
            return "high"
        elif score >= 0.5:
            return "medium"
        else:
            return "low"

    def _detect_signals(self, activity: ContributorActivity) -> List[Dict]:
        """
        Detect specific burnout signals.
        """
        signals = []

        if activity.activity_trend < -0.3:
            signals.append(
                {
                    "type": "declining_activity",
                    "severity": (
                        "moderate" if activity.activity_trend < -0.5 else "mild"
                    ),
                    "description": f"Activity declined by {abs(activity.activity_trend * 100):.0f}%",
                }
            )

        if activity.review_trend < -0.3:
            signals.append(
                {
                    "type": "reduced_reviews",
                    "severity": "moderate" if activity.review_trend < -0.5 else "mild",
                    "description": f"Reviews declined by {abs(activity.review_trend * 100):.0f}%",
                }
            )

        if activity.avg_response_time > 48:
            signals.append(
                {
                    "type": "increased_response_time",
                    "severity": (
                        "severe" if activity.avg_response_time > 72 else "moderate"
                    ),
                    "description": f"Average response time: {activity.avg_response_time:.0f} hours",
                }
            )

        if activity.sentiment_score < -0.2:
            signals.append(
                {
                    "type": "negative_sentiment",
                    "severity": (
                        "severe" if activity.sentiment_score < -0.4 else "moderate"
                    ),
                    "description": f"Negative sentiment detected (score: {activity.sentiment_score:.2f})",
                }
            )

        return signals

    def predict_burnout_risk(self, features: Dict[str, Any]) -> Tuple[float, str]:
        """
        Predict burnout risk using ML.
        """
        if not self.model:
            return 0.5, "low"

        # Prepare features
        X = np.array(
            [
                [
                    features.get("commits_trend", 0),
                    features.get("reviews_trend", 0),
                    features.get("sentiment_score", 0),
                    features.get("response_time", 0),
                    features.get("activity_trend", 0),
                ]
            ]
        )

        if self.scaler:
            X = self.scaler.transform(X)

        probability = self.model.predict_proba(X)[0][1]
        risk_level = self._determine_risk_level(probability)

        return probability, risk_level
