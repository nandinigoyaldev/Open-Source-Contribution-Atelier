"""
ML model for predicting onboarding completion.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, Tuple
from django.core.cache import cache
from apps.onboarding.models import OnboardingJourney, JourneyEvent
import logging

logger = logging.getLogger(__name__)


class OnboardingPredictor:
    """
    ML-based onboarding completion predictor.
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.features = [
            "time_in_stage_hours",
            "events_count",
            "stage_progress",
            "previous_contributions",
            "activity_frequency",
            "help_seeking_count",
        ]

    def train_model(self) -> Dict[str, float]:
        """
        Train the completion prediction model.
        """
        journeys = OnboardingJourney.objects.all()
        if journeys.count() < 10:
            return {"error": "Need at least 10 journeys for training"}

        # Prepare training data
        data = []
        labels = []

        for journey in journeys:
            features = self._extract_features(journey)
            data.append(features)
            labels.append(1 if journey.status == "completed" else 0)

        X = np.array(data)
        y = np.array(labels)

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model = LogisticRegression(random_state=42, max_iter=1000)
        self.model.fit(X_scaled, y)

        # Calculate accuracy
        from sklearn.metrics import accuracy_score

        predictions = self.model.predict(X_scaled)
        accuracy = accuracy_score(y, predictions)

        logger.info(f"Model trained with accuracy: {accuracy:.2f}")
        return {"accuracy": accuracy, "samples": len(data)}

    def predict_completion(self, journey: OnboardingJourney) -> Tuple[float, float]:
        """
        Predict completion likelihood.
        """
        if not self.model or not self.scaler:
            return 0.5, 0.0

        features = self._extract_features(journey)
        X = np.array(features).reshape(1, -1)
        X_scaled = self.scaler.transform(X)

        probability = self.model.predict_proba(X_scaled)[0][1]
        confidence = max(self.model.predict_proba(X_scaled)[0])

        return float(probability), float(confidence)

    def _extract_features(self, journey: OnboardingJourney) -> list:
        """Extract features for prediction."""
        events = JourneyEvent.objects.filter(journey=journey)

        time_in_stage = 0
        if journey.stage_started_at:
            time_in_stage = (
                timezone.now() - journey.stage_started_at
            ).total_seconds() / 3600

        return [
            min(time_in_stage / 24, 7),  # Time in stage (capped at 7 days)
            min(events.count() / 10, 10),  # Events count
            self._get_stage_progress(journey),  # Stage progress
            self._get_previous_contributions(journey),  # Previous contributions
            self._get_activity_frequency(journey),  # Activity frequency
            self._get_help_seeking_count(journey),  # Help seeking
        ]

    def _get_stage_progress(self, journey: OnboardingJourney) -> float:
        """Get progress through stages (0-1)."""
        stage_order = [
            "discovery",
            "setup",
            "first_issue",
            "pr_submitted",
            "merged",
            "completed",
        ]
        try:
            current_index = stage_order.index(journey.current_stage)
            return current_index / (len(stage_order) - 1)
        except ValueError:
            return 0.0

    def _get_previous_contributions(self, journey: OnboardingJourney) -> float:
        """Get previous contributions from user."""
        return 0.5  # Simplified

    def _get_activity_frequency(self, journey: OnboardingJourney) -> float:
        """Calculate activity frequency."""
        events = JourneyEvent.objects.filter(
            journey=journey, created_at__gte=timezone.now() - timedelta(days=7)
        )
        return min(events.count() / 14, 1.0)

    def _get_help_seeking_count(self, journey: OnboardingJourney) -> float:
        """Count help seeking events."""
        events = JourneyEvent.objects.filter(journey=journey, event_type="help_seek")
        return min(events.count() / 5, 1.0)
