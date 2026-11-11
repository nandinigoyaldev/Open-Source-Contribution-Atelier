"""
Tests for Learning Journal API views.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.learning_journal.models import (
    JournalComment,
    JournalEntry,
    JournalReaction,
    JournalTemplate,
    ReflectionPrompt,
)


class BaseJournalTest(TestCase):
    """Shared setup."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.other = User.objects.create_user(username="other", password="pass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class JournalEntryListCreateViewTest(BaseJournalTest):
    """Tests for JournalEntryListCreateView."""

    def test_list_entries(self):
        url = reverse("learning_journal:entry-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_entry(self):
        url = reverse("learning_journal:entry-list")
        data = {
            "date": timezone.now().date().isoformat(),
            "what_i_learned": "Learned Django views",
            "mood": 4,
            "productivity_score": 8,
            "hours_spent": 2.0,
            "tags": ["django", "python"],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreater(response.data["xp_earned"], 0)


class JournalEntryDetailViewTest(BaseJournalTest):
    """Tests for JournalEntryDetailView."""

    def setUp(self):
        super().setUp()
        self.entry = JournalEntry.objects.create(
            user=self.user,
            date=timezone.now().date(),
            what_i_learned="Test entry",
        )

    def test_retrieve(self):
        url = reverse("learning_journal:entry-detail", args=[self.entry.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update(self):
        url = reverse("learning_journal:entry-detail", args=[self.entry.id])
        response = self.client.patch(
            url,
            {"what_i_learned": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_two_device_concurrent_edit_conflict(self):
        url = reverse("learning_journal:entry-detail", args=[self.entry.id])
        # Device A updates with expected_version=1 -> succeeds, version becomes 2
        res_a = self.client.patch(
            url,
            {"what_i_learned": "Device A update", "expected_version": 1},
            format="json",
        )
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.version, 2)

        # Device B updates with stale expected_version=1 -> 409 Conflict
        res_b = self.client.patch(
            url,
            {"what_i_learned": "Device B update", "expected_version": 1},
            format="json",
        )
        self.assertEqual(res_b.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res_b.data["error"], "conflict")
        self.assertEqual(res_b.data["server_version"], 2)

    def test_offline_retry_with_client_id_does_not_duplicate(self):
        url = reverse("learning_journal:entry-list")
        payload = {
            "date": (timezone.now().date() - timedelta(days=2)).isoformat(),
            "what_i_learned": "Offline journal entry",
            "client_id": "journal-uuid-999",
        }
        res1 = self.client.post(url, payload, format="json")
        self.assertIn(
            res1.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK]
        )

        res2 = self.client.post(url, payload, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(
            JournalEntry.objects.filter(client_id="journal-uuid-999").count(), 1
        )

    def test_delete(self):
        url = reverse("learning_journal:entry-detail", args=[self.entry.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_access_other_users(self):
        other_entry = JournalEntry.objects.create(
            user=self.other,
            date=timezone.now().date() - timedelta(days=1),
            what_i_learned="Other's",
        )
        url = reverse("learning_journal:entry-detail", args=[other_entry.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TodayEntryViewTest(BaseJournalTest):
    """Tests for TodayEntryView."""

    def test_get_no_entry(self):
        url = reverse("learning_journal:today-entry")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["exists"])
        self.assertIn("prompt", response.data)

    def test_get_existing_entry(self):
        JournalEntry.objects.create(
            user=self.user,
            date=timezone.now().date(),
            what_i_learned="Done!",
        )
        url = reverse("learning_journal:today-entry")
        response = self.client.get(url)
        self.assertTrue(response.data.get("what_i_learned"))

    def test_create_today_entry(self):
        url = reverse("learning_journal:today-entry")
        data = {
            "what_i_learned": "Today's learning",
            "mood": 5,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_duplicate_today(self):
        url = reverse("learning_journal:today-entry")
        data = {"what_i_learned": "First"}
        self.client.post(url, data, format="json")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JournalCommentListCreateViewTest(BaseJournalTest):
    """Tests for JournalCommentListCreateView."""

    def setUp(self):
        super().setUp()
        self.entry = JournalEntry.objects.create(
            user=self.user,
            date=timezone.now().date(),
            what_i_learned="Test",
        )

    def test_list_comments(self):
        url = reverse(
            "learning_journal:entry-comments",
            args=[self.entry.id],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_comment(self):
        url = reverse(
            "learning_journal:entry-comments",
            args=[self.entry.id],
        )
        data = {"content": "Great work!"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class JournalReactionViewTest(BaseJournalTest):
    """Tests for JournalReactionView."""

    def setUp(self):
        super().setUp()
        self.entry = JournalEntry.objects.create(
            user=self.other,
            date=timezone.now().date(),
            what_i_learned="Public",
            visibility="public",
        )

    def test_add_reaction(self):
        url = reverse("learning_journal:entry-react", args=[self.entry.id])
        data = {"reaction_type": "like"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_toggle_reaction(self):
        url = reverse("learning_journal:entry-react", args=[self.entry.id])
        self.client.post(url, {"reaction_type": "like"}, format="json")
        response = self.client.post(url, {"reaction_type": "like"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["removed"])

    def test_missing_type(self):
        url = reverse("learning_journal:entry-react", args=[self.entry.id])
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JournalStreakViewTest(BaseJournalTest):
    """Tests for JournalStreakView."""

    def test_get_streak(self):
        url = reverse("learning_journal:journal-streak")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("current_streak", response.data)


class JournalStatsViewTest(BaseJournalTest):
    """Tests for JournalStatsView."""

    def test_get_stats(self):
        url = reverse("learning_journal:journal-stats")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_entries", response.data)


class WeeklySummaryViewTest(BaseJournalTest):
    """Tests for WeeklySummaryView."""

    def test_get_summary(self):
        url = reverse("learning_journal:weekly-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("summary", response.data)

    def test_invalid_date(self):
        url = reverse("learning_journal:weekly-summary")
        response = self.client.get(url, {"week_start": "bad"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JournalSocialFeedViewTest(BaseJournalTest):
    """Tests for JournalSocialFeedView."""

    def test_get_feed(self):
        url = reverse("learning_journal:social-feed")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ReflectionPromptViewTest(BaseJournalTest):
    """Tests for ReflectionPromptView."""

    def test_get_prompt(self):
        url = reverse("learning_journal:reflection-prompt")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text", response.data)

    def test_with_custom_prompt(self):
        ReflectionPrompt.objects.create(text="Custom?", prompt_type="daily")
        url = reverse("learning_journal:reflection-prompt")
        response = self.client.get(url)
        self.assertEqual(response.data["text"], "Custom?")


class JournalTemplateListCreateViewTest(BaseJournalTest):
    """Tests for JournalTemplateListCreateView."""

    def test_list_templates(self):
        url = reverse("learning_journal:template-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_template(self):
        url = reverse("learning_journal:template-list")
        data = {
            "name": "My Template",
            "sections": ["What I learned", "Goals"],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class WeeklyReflectionListViewTest(BaseJournalTest):
    """Tests for WeeklyReflectionListView."""

    def test_list_empty(self):
        url = reverse("learning_journal:weekly-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


from django.utils import timezone
