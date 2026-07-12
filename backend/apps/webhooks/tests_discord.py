"""
Tests for Discord Webhook Integration.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .discord import AchievementData, announce_achievement, send_achievement_embed

User = get_user_model()


class DiscordWebhookTests(TestCase):
    """Test cases for Discord webhook functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @patch("apps.webhooks.discord.requests.post")
    @patch("apps.webhooks.discord.get_discord_webhook_url")
    def test_send_achievement_embed_success(self, mock_get_url, mock_post):
        """Test successful Discord webhook send."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        achievement = AchievementData(
            user_id=self.user.id,
            username=self.user.username,
            achievement_name="First Commit",
            achievement_icon="https://example.com/badge.png",
            description="Made your first commit!",
            tier="bronze",
        )

        result = send_achievement_embed(achievement)

        self.assertTrue(result)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://discord.com/api/webhooks/test")

    @patch("apps.webhooks.discord.get_discord_webhook_url")
    def test_send_achievement_embed_no_url(self, mock_get_url):
        """Test that no webhook call is made when URL is not configured."""
        mock_get_url.return_value = None

        achievement = AchievementData(
            user_id=self.user.id,
            username=self.user.username,
            achievement_name="First Commit",
            achievement_icon="",
            description="Made your first commit!",
        )

        result = send_achievement_embed(achievement)

        self.assertFalse(result)

    @patch("apps.webhooks.discord.requests.post")
    @patch("apps.webhooks.discord.get_discord_webhook_url")
    def test_send_achievement_embed_failure(self, mock_get_url, mock_post):
        """Test handling of Discord webhook failure."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        achievement = AchievementData(
            user_id=self.user.id,
            username=self.user.username,
            achievement_name="First Commit",
            achievement_icon="",
            description="Made your first commit!",
        )

        result = send_achievement_embed(achievement)

        self.assertFalse(result)

    @patch("apps.webhooks.discord.requests.post")
    @patch("apps.webhooks.discord.get_discord_webhook_url")
    def test_announce_achievement_convenience(self, mock_get_url, mock_post):
        """Test the announce_achievement convenience function."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        result = announce_achievement(
            user=self.user,
            achievement_name="Pathway Completed",
            achievement_icon="https://example.com/pathway.png",
            description="Completed the Git Basics pathway!",
            pathway_name="Git Basics",
            tier="gold",
        )

        self.assertTrue(result)

        # Verify the embed content
        call_args = mock_post.call_args
        embed = call_args[1]["json"]["embeds"][0]
        self.assertEqual(embed["title"], "🏆 Achievement Unlocked!")
        self.assertEqual(embed["description"], "**Pathway Completed**")
        self.assertEqual(embed["color"], 0xFFD700)  # Gold color

    @patch("apps.webhooks.discord.requests.post")
    @patch("apps.webhooks.discord.get_discord_webhook_url")
    def test_tier_colors(self, mock_get_url, mock_post):
        """Test that different tiers produce correct colors."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"

        tier_colors = {
            "bronze": 0xCD7F32,
            "silver": 0xC0C0C0,
            "gold": 0xFFD700,
            "platinum": 0xE5E4E2,
        }

        for tier, expected_color in tier_colors.items():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            mock_post.reset_mock()

            achievement = AchievementData(
                user_id=self.user.id,
                username=self.user.username,
                achievement_name=f"{tier.title()} Badge",
                achievement_icon="",
                description="",
                tier=tier,
            )

            send_achievement_embed(achievement)

            call_args = mock_post.call_args
            embed = call_args[1]["json"]["embeds"][0]
            self.assertEqual(
                embed["color"], expected_color, f"Color mismatch for {tier}"
            )

    @patch("apps.webhooks.discord.requests.post")
    @patch("apps.webhooks.discord.get_discord_webhook_url")
    def test_custom_webhook_url(self, mock_get_url, mock_post):
        """Test that custom webhook URL is used when provided."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/default"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        achievement = AchievementData(
            user_id=self.user.id,
            username=self.user.username,
            achievement_name="Test",
            achievement_icon="",
            description="",
        )

        custom_url = "https://discord.com/api/webhooks/custom"
        send_achievement_embed(achievement, webhook_url=custom_url)

        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], custom_url)
