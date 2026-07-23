"""
Discord Webhook Integration for Achievement Announcements.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Model

logger = logging.getLogger(__name__)


@dataclass
class AchievementData:
    """Data class for achievement information."""

    user_id: int
    username: str
    achievement_name: str
    achievement_icon: str
    description: str
    badge_id: Optional[int] = None
    pathway_name: Optional[str] = None
    tier: Optional[str] = None  # bronze, silver, gold, platinum


def get_discord_webhook_url() -> Optional[str]:
    """Get Discord webhook URL from settings."""
    return getattr(settings, "DISCORD_WEBHOOK_URL", None)


def send_achievement_embed(
    achievement: AchievementData,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Send an achievement announcement to Discord via webhook.

    Creates a rich Discord embed with:
    - User avatar
    - Achievement icon
    - Achievement name and description
    - Badge/tier information

    Args:
        achievement: AchievementData with user and achievement info
        webhook_url: Optional override for webhook URL (uses settings if not provided)

    Returns:
        True if successful, False otherwise
    """
    url = webhook_url or get_discord_webhook_url()

    if not url:
        logger.debug("Discord webhook URL not configured")
        return False

    # Tier colors (Discord color values)
    tier_colors = {
        "bronze": 0xCD7F32,
        "silver": 0xC0C0C0,
        "gold": 0xFFD700,
        "platinum": 0xE5E4E2,
        "diamond": 0xB9F2FF,
    }
    default_color = 0x7CFC00  # Lawn green

    embed = {
        "embeds": [
            {
                "title": f"🏆 Achievement Unlocked!",
                "description": f"**{achievement.achievement_name}**",
                "color": tier_colors.get(achievement.tier, default_color),
                "fields": [
                    {
                        "name": "👤 User",
                        "value": achievement.username,
                        "inline": True,
                    },
                ],
                "footer": {
                    "text": "Open Source Contribution Atelier",
                },
            }
        ]
    }

    # Add description field
    if achievement.description:
        embed["embeds"][0]["fields"].append(
            {
                "name": "📝 Details",
                "value": achievement.description,
                "inline": False,
            }
        )

    # Add badge/pathway info if available
    if achievement.pathway_name:
        embed["embeds"][0]["fields"].append(
            {
                "name": "🛤️ Pathway",
                "value": achievement.pathway_name,
                "inline": True,
            }
        )

    if achievement.tier:
        tier_emoji = {
            "bronze": "🥉",
            "silver": "🥈",
            "gold": "🥇",
            "platinum": "💎",
            "diamond": "💠",
        }
        embed["embeds"][0]["fields"].append(
            {
                "name": "⭐ Tier",
                "value": f"{tier_emoji.get(achievement.tier, '')} {achievement.tier.title()}",
                "inline": True,
            }
        )

    # Add thumbnail with achievement icon
    if achievement.achievement_icon:
        embed["embeds"][0]["thumbnail"] = {
            "url": achievement.achievement_icon,
        }

    try:
        response = requests.post(url, json=embed, timeout=10)
        if response.status_code in (200, 204):
            logger.info(
                f"Discord webhook sent for achievement: {achievement.achievement_name}"
            )
            return True
        else:
            logger.warning(
                f"Discord webhook failed with status {response.status_code}: {response.text}"
            )
            return False
    except requests.RequestException as e:
        logger.error(f"Discord webhook request failed: {e}")
        return False


def announce_achievement(
    user: Model,
    achievement_name: str,
    achievement_icon: str = "",
    description: str = "",
    pathway_name: Optional[str] = None,
    tier: Optional[str] = None,
) -> bool:
    """
    Convenience function to announce an achievement.

    Args:
        user: Django user model instance
        achievement_name: Name of the achievement
        achievement_icon: URL to achievement icon image
        description: Description of the achievement
        pathway_name: Optional learning pathway name
        tier: Optional achievement tier (bronze, silver, gold, platinum)

    Returns:
        True if successful, False otherwise
    """
    achievement = AchievementData(
        user_id=user.id,
        username=user.username,
        achievement_name=achievement_name,
        achievement_icon=achievement_icon,
        description=description,
        pathway_name=pathway_name,
        tier=tier,
    )
    return send_achievement_embed(achievement)
