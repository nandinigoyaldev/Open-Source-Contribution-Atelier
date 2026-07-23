"""
NLP-based sentiment analysis for contributor communications.
"""

from textblob import TextBlob
from typing import List, Dict, Any
import re
from apps.burnout_detection.models import BurnoutSignal
import logging

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    Analyze sentiment in contributor communications.
    """

    def __init__(self):
        self.negative_patterns = [
            r"frustrat",
            r"confus",
            r"overwhelm",
            r"stress",
            r"burnout",
            r"tired",
            r"give up",
            r"quitting",
            r"unfair",
            r"ignored",
            r"repeat",
            r"too hard",
        ]

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        """
        blob = TextBlob(text)

        # Get sentiment polarity (-1 to 1)
        polarity = blob.sentiment.polarity

        # Detect negative patterns
        negative_patterns_detected = []
        for pattern in self.negative_patterns:
            if re.search(pattern, text.lower()):
                negative_patterns_detected.append(pattern)

        # Determine sentiment label
        if polarity > 0.3:
            sentiment = "positive"
        elif polarity < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "polarity": polarity,
            "sentiment": sentiment,
            "negative_patterns": negative_patterns_detected,
            "is_negative": polarity < -0.1 or bool(negative_patterns_detected),
        }

    def analyze_comments(self, comments: List[Dict]) -> Dict[str, Any]:
        """
        Analyze sentiment of multiple comments.
        """
        sentiments = []
        negative_count = 0

        for comment in comments:
            body = comment.get("body", "")
            if body:
                result = self.analyze_text(body)
                sentiments.append(result)
                if result["is_negative"]:
                    negative_count += 1

        if not sentiments:
            return {
                "average_sentiment": 0.0,
                "negative_ratio": 0.0,
                "is_negative_trend": False,
                "sentiment_trend": 0.0,
            }

        avg_polarity = sum(s["polarity"] for s in sentiments) / len(sentiments)
        negative_ratio = negative_count / len(sentiments)

        # Detect trend (simplified)
        recent_sentiments = sentiments[-10:] if len(sentiments) > 10 else sentiments
        recent_avg = sum(s["polarity"] for s in recent_sentiments) / len(
            recent_sentiments
        )
        trend = recent_avg - avg_polarity

        return {
            "average_sentiment": avg_polarity,
            "negative_ratio": negative_ratio,
            "is_negative_trend": trend < 0,
            "sentiment_trend": trend,
        }
