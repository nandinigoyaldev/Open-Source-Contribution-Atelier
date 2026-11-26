from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.progress.models import (
    Badge,
    FinancialReward,
    RewardTransactionSaga,
    UserBadge,
    XPEvent,
)
from apps.progress.serializers import (
    FinancialRewardSerializer,
    RewardTransactionSagaSerializer,
)
from apps.progress.services.rewards_saga import (
    BadgeRewardAllocationStep,
    ExternalRewardAPIStep,
    FinancialRewardAllocationStep,
    LambdaSagaStep,
    RewardsSagaOrchestrator,
    SagaExecutionError,
    XPBatchAllocationStep,
    execute_cross_table_reward_allocation,
)

User = get_user_model()


class RewardsSagaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sagatester", email="saga@example.com", password="password123"
        )
        self.badge = Badge.objects.create(
            slug="code-champion",
            name="Code Champion",
            description="Achieved high milestone",
        )

    def test_successful_cross_table_reward_saga(self):
        """
        Happy path: Allocates batch XP and Financial Reward.
        Saga transitions from PREPARING to COMMITTED with all step records completed.
        """
        xp_items = [
            {
                "base_points": 50,
                "multiplier": 1.0,
                "source_type": "challenge",
                "source_id": 101,
            },
            {
                "base_points": 100,
                "multiplier": 1.5,
                "xp_delta": 150,
                "source_type": "challenge",
                "source_id": 102,
            },
        ]
        fin_reward = {
            "amount": "50.00",
            "currency": "USD",
            "source_type": "hackathon_prize",
            "source_id": "hack_2026",
            "metadata": {"tier": "gold"},
        }

        saga = execute_cross_table_reward_allocation(
            user=self.user,
            xp_items=xp_items,
            financial_reward=fin_reward,
            badge_slug="code-champion",
            action_type="hackathon_winner_allocation",
        )

        # 1. State transition to COMMITTED
        self.assertEqual(saga.status, RewardTransactionSaga.Status.COMMITTED)
        self.assertEqual(saga.error_message, "")

        # 2. XPEvent records committed
        xp_events = XPEvent.objects.filter(user=self.user)
        self.assertEqual(xp_events.count(), 2)
        total_xp = sum(e.xp_delta for e in xp_events)
        self.assertEqual(total_xp, 200)  # 50 + 150

        # 3. FinancialReward record committed
        rewards = FinancialReward.objects.filter(user=self.user)
        self.assertEqual(rewards.count(), 1)
        reward = rewards.first()
        self.assertEqual(reward.status, FinancialReward.Status.ALLOCATED)
        self.assertEqual(reward.amount, Decimal("50.00"))
        self.assertEqual(reward.currency, "USD")
        self.assertEqual(reward.saga_id, saga.saga_id)

        # 4. Badge awarded
        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=self.badge).exists()
        )

        # 5. Step states journal
        completed_steps = [
            s["step"] for s in saga.step_states if s.get("status") == "COMPLETED"
        ]
        self.assertIn("xp_batch_allocation", completed_steps)
        self.assertIn("financial_reward_allocation", completed_steps)
        self.assertIn("badge_reward_allocation", completed_steps)

    def test_external_api_failure_triggers_compensatory_rollback(self):
        """
        Failure scenario: External API throws exception.
        Orchestrator transitions through PREPARING -> COMPENSATING -> ABORTED,
        and automatically executes compensatory rollbacks:
          - FinancialReward is REVOKED
          - XPEvent rows are deleted
        """
        xp_items = [{"base_points": 80, "source_type": "challenge", "source_id": 201}]
        fin_reward = {
            "amount": "100.00",
            "currency": "EUR",
            "source_type": "bounty_reward",
            "source_id": "bounty_99",
        }

        def failing_external_api(ctx):
            raise ConnectionError(
                "Payment gateway timed out: unable to disburse payout"
            )

        orchestrator = RewardsSagaOrchestrator(
            user=self.user,
            saga_id="saga_external_fail_test",
            action_type="bounty_payout",
        )
        orchestrator.add_step(XPBatchAllocationStep(self.user, xp_items))
        orchestrator.add_step(
            FinancialRewardAllocationStep(
                self.user,
                amount=fin_reward["amount"],
                currency=fin_reward["currency"],
                source_type=fin_reward["source_type"],
                source_id=fin_reward["source_id"],
            )
        )
        orchestrator.add_step(
            ExternalRewardAPIStep(
                call_fn=failing_external_api,
                step_name="stripe_payout_api",
            )
        )

        with self.assertRaises(SagaExecutionError) as ctx:
            orchestrator.execute(raise_on_failure=True)

        self.assertIn("Payment gateway timed out", str(ctx.exception))

        # Check Saga record state
        saga = RewardTransactionSaga.objects.get(saga_id="saga_external_fail_test")
        self.assertEqual(saga.status, RewardTransactionSaga.Status.ABORTED)
        self.assertIn("Payment gateway timed out", saga.error_message)

        # Compensatory rollback verification:
        # 1. Financial reward must be REVOKED, not allocated
        reward = FinancialReward.objects.get(saga_id="saga_external_fail_test")
        self.assertEqual(reward.status, FinancialReward.Status.REVOKED)

        # 2. XPEvent must be completely deleted/rolled back
        self.assertEqual(XPEvent.objects.filter(user=self.user).count(), 0)

        # 3. Step states journal records compensation
        states = {s["step"]: s["status"] for s in saga.step_states}
        self.assertEqual(states.get("financial_reward_allocation"), "COMPENSATED")
        self.assertEqual(states.get("xp_batch_allocation"), "COMPENSATED")

    def test_subsequent_db_step_failure_triggers_preceding_compensations(self):
        """
        Failure scenario: A subsequent database step throws an unhandled error.
        All preceding actions must be compensated in reverse order.
        """
        xp_items = [{"base_points": 40, "source_type": "lesson", "source_id": 12}]

        def bad_step_execute(ctx):
            raise ValueError("Integrity failure in accounting ledger")

        def bad_step_compensate(ctx):
            return {"rolled_back": True}

        orchestrator = RewardsSagaOrchestrator(
            user=self.user,
            saga_id="saga_db_fail_test",
        )
        orchestrator.add_step(XPBatchAllocationStep(self.user, xp_items))
        orchestrator.add_step(
            LambdaSagaStep(
                name="ledger_entry_step",
                execute_fn=bad_step_execute,
                compensate_fn=bad_step_compensate,
            )
        )

        with self.assertRaises(SagaExecutionError):
            orchestrator.execute()

        saga = RewardTransactionSaga.objects.get(saga_id="saga_db_fail_test")
        self.assertEqual(saga.status, RewardTransactionSaga.Status.ABORTED)
        self.assertIn("Integrity failure in accounting ledger", saga.error_message)

        # Preceding XP allocation compensated
        self.assertEqual(XPEvent.objects.filter(user=self.user).count(), 0)

    def test_badge_step_award_and_compensatory_revocation(self):
        """
        Badge is granted, but downstream failure triggers badge revocation.
        """
        orchestrator = RewardsSagaOrchestrator(
            user=self.user,
            saga_id="saga_badge_revocation_test",
        )
        orchestrator.add_step(
            BadgeRewardAllocationStep(self.user, badge_slug="code-champion")
        )
        orchestrator.add_step(
            LambdaSagaStep(
                name="failing_step",
                execute_fn=lambda ctx: 1 / 0,
                compensate_fn=lambda ctx: None,
            )
        )

        with self.assertRaises(SagaExecutionError):
            orchestrator.execute()

        saga = RewardTransactionSaga.objects.get(saga_id="saga_badge_revocation_test")
        self.assertEqual(saga.status, RewardTransactionSaga.Status.ABORTED)

        # UserBadge was rolled back
        self.assertFalse(
            UserBadge.objects.filter(user=self.user, badge=self.badge).exists()
        )

    def test_raise_on_failure_false_returns_aborted_saga(self):
        """
        When raise_on_failure=False, execute() returns the aborted saga record
        without re-raising SagaExecutionError.
        """
        orchestrator = RewardsSagaOrchestrator(
            user=self.user,
            saga_id="saga_no_raise_test",
        )
        orchestrator.add_step(
            LambdaSagaStep(
                name="failing_step",
                execute_fn=lambda ctx: (_ for _ in ()).throw(
                    RuntimeError("Silent failure")
                ),
                compensate_fn=lambda ctx: None,
            )
        )

        saga = orchestrator.execute(raise_on_failure=False)
        self.assertEqual(saga.status, RewardTransactionSaga.Status.ABORTED)
        self.assertIn("Silent failure", saga.error_message)

    def test_resilience_to_individual_compensation_error(self):
        """
        If one step's compensate() throws an unexpected error, other steps
        continue to be compensated and COMPENSATION_FAILED is recorded.
        """

        def bad_compensator(ctx):
            raise RuntimeError("Compensation error in external gateway")

        orchestrator = RewardsSagaOrchestrator(
            user=self.user,
            saga_id="saga_comp_error_resilience",
        )
        # Step 1: XP allocation (clean compensation)
        orchestrator.add_step(
            XPBatchAllocationStep(
                self.user, [{"base_points": 25, "source_type": "exercise"}]
            )
        )
        # Step 2: Step with broken compensation
        orchestrator.add_step(
            LambdaSagaStep(
                name="flaky_service_step",
                execute_fn=lambda ctx: {"token": "xyz"},
                compensate_fn=bad_compensator,
            )
        )
        # Step 3: Trigger failure
        orchestrator.add_step(
            LambdaSagaStep(
                name="trigger_failure",
                execute_fn=lambda ctx: (_ for _ in ()).throw(ValueError("Trigger")),
                compensate_fn=lambda ctx: None,
            )
        )

        with self.assertRaises(SagaExecutionError) as err:
            orchestrator.execute()

        # Step 1 XP allocation was still compensated despite Step 2 compensation failure!
        self.assertEqual(XPEvent.objects.filter(user=self.user).count(), 0)

        saga = RewardTransactionSaga.objects.get(saga_id="saga_comp_error_resilience")
        self.assertEqual(saga.status, RewardTransactionSaga.Status.ABORTED)

        statuses = {s["step"]: s["status"] for s in saga.step_states}
        self.assertEqual(statuses.get("flaky_service_step"), "COMPENSATION_FAILED")
        self.assertEqual(statuses.get("xp_batch_allocation"), "COMPENSATED")
        self.assertEqual(len(err.exception.compensation_errors), 1)

    def test_idempotent_step_compensations(self):
        """
        Calling compensate() multiple times or with empty context is idempotent
        and does not raise errors.
        """
        xp_step = XPBatchAllocationStep(self.user, [])
        fin_step = FinancialRewardAllocationStep(self.user, amount="10.00")

        # Empty context
        res_xp = xp_step.compensate({})
        self.assertEqual(res_xp["deleted_count"], 0)

        res_fin = fin_step.compensate({})
        self.assertEqual(res_fin["revoked_count"], 0)

    def test_serializers_for_saga_and_financial_reward(self):
        """
        Ensure REST framework serializers properly serialize saga and financial reward models.
        """
        saga = RewardTransactionSaga.objects.create(
            saga_id="saga_serial_001",
            user=self.user,
            status=RewardTransactionSaga.Status.COMMITTED,
            action_type="test_action",
            payload={"key": "val"},
            step_states=[{"step": "s1", "status": "COMPLETED"}],
        )
        fin = FinancialReward.objects.create(
            user=self.user,
            saga_id="saga_serial_001",
            amount=Decimal("15.50"),
            currency="USD",
            source_type="lesson_bounty",
            status=FinancialReward.Status.ALLOCATED,
        )

        saga_data = RewardTransactionSagaSerializer(saga).data
        self.assertEqual(saga_data["saga_id"], "saga_serial_001")
        self.assertEqual(saga_data["status"], "COMMITTED")
        self.assertEqual(saga_data["username"], "sagatester")

        fin_data = FinancialRewardSerializer(fin).data
        self.assertEqual(fin_data["amount"], "15.50")
        self.assertEqual(fin_data["currency"], "USD")
        self.assertEqual(fin_data["status"], "allocated")
        self.assertEqual(fin_data["username"], "sagatester")
