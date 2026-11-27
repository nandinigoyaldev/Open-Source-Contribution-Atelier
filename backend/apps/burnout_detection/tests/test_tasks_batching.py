from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.burnout_detection.models import (
    BurnoutActivityDay,
    BurnoutSignal,
    ContributorActivity,
)
from apps.burnout_detection.tasks import detect_burnout, detect_user_burnout_risk


class BurnoutTaskBatchingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.users = [
            User.objects.create_user(
                username=f"batch-user-{i}", password="test-password"
            )
            for i in range(5)
        ]
        for user in self.users:
            user.user_profile.weekend_learning_enabled = True
            user.user_profile.save(update_fields=["weekend_learning_enabled"])

        today = timezone.localdate()
        dates = [today - timedelta(days=i) for i in range(4, -1, -1)]
        # Flag users 0, 2, 4 across multiple batches (batch_size=2).
        for idx in (0, 2, 4):
            BurnoutActivityDay.objects.bulk_create(
                [
                    BurnoutActivityDay(user=self.users[idx], date=day, active_hours=8.5)
                    for day in dates
                ]
            )

    @patch("apps.burnout_detection.tasks.trigger_intervention.delay")
    def test_detect_user_burnout_risk_across_batches_is_idempotent(self, delay):
        result = detect_user_burnout_risk(batch_size=2)

        self.assertEqual(result["flagged"], 3)
        self.assertEqual(delay.call_count, 3)
        self.assertEqual(
            BurnoutSignal.objects.filter(
                signal_type="irregular_pattern", is_resolved=False
            ).count(),
            3,
        )

        # Re-running must be idempotent and not duplicate signals or triggers.
        delay.reset_mock()
        rerun = detect_user_burnout_risk(batch_size=2)
        self.assertEqual(rerun["flagged"], 0)
        delay.assert_not_called()

    @patch("apps.burnout_detection.tasks.trigger_intervention.delay")
    def test_detect_user_burnout_risk_query_count_is_bounded(self, _delay):
        with self.assertNumQueries(5):
            # 1: user batch, 2: days batch, 3: existing signals, 4: bulk_create,
            # 5: trailing empty keyset page check
            result = detect_user_burnout_risk(batch_size=500)
        self.assertEqual(result["flagged"], 3)

    @patch("apps.burnout_detection.tasks.trigger_intervention.delay")
    def test_detect_burnout_uuids_across_batches_and_idempotency(self, delay):
        for user in self.users[:3]:
            ContributorActivity.objects.create(user=user)

        fake_detection = {
            "needs_intervention": True,
            "risk_level": "critical",
            "signals": [
                {
                    "type": "declining_activity",
                    "severity": "high",
                    "description": "Sharp drop in weekly activity",
                }
            ],
        }
        with patch(
            "apps.burnout_detection.tasks.BurnoutDetector.detect_burnout",
            return_value=fake_detection,
        ):
            result = detect_burnout(batch_size=2)
            self.assertEqual(result, {"detected": 3, "critical": 3})
            self.assertEqual(BurnoutSignal.objects.count(), 3)
            self.assertEqual(delay.call_count, 3)

            delay.reset_mock()
            detect_burnout(batch_size=2)
            self.assertEqual(BurnoutSignal.objects.count(), 3)
            delay.assert_not_called()
