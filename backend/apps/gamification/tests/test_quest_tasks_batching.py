from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.gamification.models import Quest, UserQuest
from apps.gamification.tasks import assign_daily_quests, expire_old_quests


class QuestTasksBatchingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.active_users = [
            User.objects.create_user(
                username=f"quest-user-{i}", password="test-password", is_active=True
            )
            for i in range(5)
        ]
        self.inactive_user = User.objects.create_user(
            username="quest-inactive", password="test-password", is_active=False
        )

        self.daily_q1 = Quest.objects.create(
            title="Daily 1",
            description="Complete 1 lesson",
            quest_type="complete_lessons",
            frequency="daily",
            is_active=True,
        )
        self.daily_q2 = Quest.objects.create(
            title="Daily 2",
            description="Run sandbox",
            quest_type="use_sandbox",
            frequency="daily",
            is_active=True,
        )
        self.weekly_q = Quest.objects.create(
            title="Weekly 1",
            description="Earn XP",
            quest_type="earn_xp",
            frequency="weekly",
            is_active=True,
        )
        self.inactive_q = Quest.objects.create(
            title="Inactive",
            description="Ignored",
            quest_type="earn_xp",
            frequency="daily",
            is_active=False,
        )

    def test_assign_daily_quests_across_batches_and_idempotency(self):
        created = assign_daily_quests(batch_size=2)
        # 5 active users * (2 daily + 1 weekly) = 15
        self.assertEqual(created, 15)
        self.assertEqual(UserQuest.objects.count(), 15)
        self.assertFalse(UserQuest.objects.filter(user=self.inactive_user).exists())
        self.assertFalse(UserQuest.objects.filter(quest=self.inactive_q).exists())

        # Idempotent re-run creates zero additional rows
        created_again = assign_daily_quests(batch_size=2)
        self.assertEqual(created_again, 0)
        self.assertEqual(UserQuest.objects.count(), 15)

    def test_assign_daily_quests_query_count_is_bounded(self):
        # 1: daily quests, 2: weekly quests, 3: user batch,
        # 4: existing daily, 5: existing weekly, 6: bulk_create,
        # 7: trailing empty user page check
        with self.assertNumQueries(7):
            created = assign_daily_quests(batch_size=500)
        self.assertEqual(created, 15)

    def test_expire_old_quests_deletes_in_batches(self):
        now = timezone.now()
        past = now - timedelta(hours=2)
        future = now + timedelta(hours=12)

        for user in self.active_users:
            UserQuest.objects.create(
                user=user, quest=self.daily_q1, expires_at=past, completed=False
            )
            UserQuest.objects.create(
                user=user, quest=self.daily_q2, expires_at=past, completed=True
            )
            UserQuest.objects.create(
                user=user, quest=self.weekly_q, expires_at=future, completed=False
            )

        deleted = expire_old_quests(batch_size=2)
        self.assertEqual(deleted, 5)
        # Completed expired + active uncompleted remain (5 + 5 = 10)
        self.assertEqual(UserQuest.objects.count(), 10)
