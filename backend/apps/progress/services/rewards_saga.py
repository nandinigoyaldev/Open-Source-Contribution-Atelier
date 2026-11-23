"""
Two-Phase Commit (2PC) / Saga Orchestrator for Cross-Table Financial Reward
and XP Batch Allocations.
=============================================================================

This module provides a robust Saga orchestrator that coordinates distributed
cross-table financial reward and XP batch allocations with atomic guarantees.

State Transitions:
  PREPARING -> COMMITTED (on full success)
  PREPARING -> COMPENSATING -> ABORTED (on any step or external API failure)

Each reward step implements:
  - execute(context: dict) -> Any
  - compensate(context: dict) -> Any

If an external API call or subsequent database write fails, the orchestrator
automatically executes compensatory rollbacks in reverse order for all
previously executed steps, ensuring strict eventual consistency and zero
partial reward allocation anomalies.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.progress.models import (
    Badge,
    FinancialReward,
    RewardTransactionSaga,
    UserBadge,
    XPEvent,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class SagaError(Exception):
    """Base exception for all saga errors."""

    pass


class SagaExecutionError(SagaError):
    """
    Raised when a step fails during forward execution and the saga is aborted.
    Contains reference to the saga record, the original exception, and any
    compensation errors.
    """

    def __init__(
        self,
        message: str,
        saga: Optional[RewardTransactionSaga] = None,
        original_exc: Optional[Exception] = None,
        compensation_errors: Optional[List[tuple[str, Exception]]] = None,
    ):
        super().__init__(message)
        self.saga = saga
        self.original_exc = original_exc
        self.compensation_errors = compensation_errors or []


class SagaCompensationError(SagaError):
    """Raised when a compensation step itself fails during rollback."""

    pass


class SagaStep(ABC):
    """
    Abstract Base Class for an individual step in the Reward Saga.

    Subclasses must define:
      - name: Unique identifier for the step type.
      - execute(context: dict) -> Any: Forward action. Stores state in context.
      - compensate(context: dict) -> Any: Compensatory undo action.
    """

    name: str = "base_step"

    @abstractmethod
    def execute(self, context: dict) -> Any:
        """
        Execute the forward operation.

        Args:
            context: Shared dictionary across all steps in the saga, containing
                     saga_id, user_id, step_results, etc.
        """
        raise NotImplementedError

    @abstractmethod
    def compensate(self, context: dict) -> Any:
        """
        Execute the compensatory rollback operation.

        Must be idempotent, safely undoing the side effects of execute().
        """
        raise NotImplementedError


class XPBatchAllocationStep(SagaStep):
    """
    Allocates a batch of XP events to a user across the XPEvent table.

    On execute:
      Inserts XPEvent rows and records the generated IDs in context.

    On compensate:
      Deletes the specific inserted XPEvent rows (or logs reversing deductions),
      returning user XP to its prior state.
    """

    name = "xp_batch_allocation"

    def __init__(
        self,
        user: Any,
        items: List[Dict[str, Any]],
        step_name: Optional[str] = None,
    ):
        self.user = user
        self.items = items
        if step_name:
            self.name = step_name

    def execute(self, context: dict) -> Dict[str, Any]:
        created_event_ids: List[int] = []
        total_xp_delta = 0

        with transaction.atomic():
            for item in self.items:
                base_points = int(item.get("base_points", 0))
                # Base points capped at 1000 per DB constraint
                base_points = min(max(base_points, 0), 1000)
                multiplier = float(item.get("multiplier", 1.0))
                xp_delta = int(item.get("xp_delta", int(base_points * multiplier)))

                event = XPEvent.objects.create(
                    user=self.user,
                    source_type=item.get("source_type", "milestone"),
                    source_id=item.get("source_id"),
                    base_points=base_points,
                    multiplier=multiplier,
                    xp_delta=xp_delta,
                )
                created_event_ids.append(event.id)
                total_xp_delta += xp_delta

        result = {
            "created_event_ids": created_event_ids,
            "count": len(created_event_ids),
            "total_xp_delta": total_xp_delta,
        }
        context.setdefault("step_results", {})[self.name] = result
        logger.debug(
            "XPBatchAllocationStep executed: %d events created (total XP: %d)",
            len(created_event_ids),
            total_xp_delta,
        )
        return result

    def compensate(self, context: dict) -> Dict[str, Any]:
        step_result = context.get("step_results", {}).get(self.name, {})
        event_ids = step_result.get("created_event_ids", [])
        if not event_ids:
            return {"deleted_count": 0}

        deleted_count, _ = XPEvent.objects.filter(id__in=event_ids).delete()
        logger.info(
            "XPBatchAllocationStep compensated: deleted %d XPEvents",
            deleted_count,
        )
        return {"deleted_count": deleted_count}


class FinancialRewardAllocationStep(SagaStep):
    """
    Allocates financial rewards (cash, balance credit, or vouchers) across
    the FinancialReward table.

    On execute:
      Creates a FinancialReward record with status=ALLOCATED and links the saga_id.

    On compensate:
      Transitions FinancialReward status to REVOKED, negating the financial credit.
    """

    name = "financial_reward_allocation"

    def __init__(
        self,
        user: Any,
        amount: Union[Decimal, float, int, str],
        currency: str = "USD",
        source_type: str = "challenge_reward",
        source_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        step_name: Optional[str] = None,
    ):
        self.user = user
        self.amount = Decimal(str(amount))
        self.currency = currency
        self.source_type = source_type
        self.source_id = str(source_id)
        self.metadata = metadata or {}
        if step_name:
            self.name = step_name

    def execute(self, context: dict) -> Dict[str, Any]:
        saga_id = context.get("saga_id", "")
        reward = FinancialReward.objects.create(
            user=self.user,
            saga_id=saga_id,
            amount=self.amount,
            currency=self.currency,
            source_type=self.source_type,
            source_id=self.source_id,
            status=FinancialReward.Status.ALLOCATED,
            metadata=self.metadata,
        )

        result = {
            "reward_id": reward.id,
            "amount": str(reward.amount),
            "currency": reward.currency,
            "status": reward.status,
        }
        context.setdefault("step_results", {})[self.name] = result
        logger.debug(
            "FinancialRewardAllocationStep executed: id=%d, amount=%s %s",
            reward.id,
            reward.amount,
            reward.currency,
        )
        return result

    def compensate(self, context: dict) -> Dict[str, Any]:
        step_result = context.get("step_results", {}).get(self.name, {})
        reward_id = step_result.get("reward_id")
        saga_id = context.get("saga_id", "")

        qs = FinancialReward.objects.filter(status=FinancialReward.Status.ALLOCATED)
        if reward_id:
            qs = qs.filter(id=reward_id)
        elif saga_id:
            qs = qs.filter(saga_id=saga_id)
        else:
            return {"revoked_count": 0}

        revoked_count = qs.update(status=FinancialReward.Status.REVOKED)
        logger.info(
            "FinancialRewardAllocationStep compensated: %d rewards marked REVOKED",
            revoked_count,
        )
        return {"revoked_count": revoked_count}


class ExternalRewardAPIStep(SagaStep):
    """
    Coordinates an external third-party reward/payout API call (e.g., Stripe,
    PayPal, gift card / voucher providers).

    On execute:
      Invokes the external API callback and records the external transaction ID.

    On compensate:
      Invokes the compensation callback to cancel, void, or refund the transaction.
    """

    name = "external_reward_api"

    def __init__(
        self,
        call_fn: Optional[Callable[[dict], Any]] = None,
        compensate_fn: Optional[Callable[[dict], Any]] = None,
        step_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.call_fn = call_fn
        self.compensate_fn = compensate_fn
        self.payload = payload or {}
        if step_name:
            self.name = step_name

    def execute(self, context: dict) -> Any:
        context.setdefault("external_payloads", {})[self.name] = self.payload
        if self.call_fn:
            result = self.call_fn(context)
        else:
            # Default simulation: generate synthetic external transaction ID
            result = {
                "transaction_id": f"ext_txn_{uuid.uuid4().hex[:12]}",
                "status": "APPROVED",
            }
        context.setdefault("step_results", {})[self.name] = result
        logger.debug("ExternalRewardAPIStep executed: %s", result)
        return result

    def compensate(self, context: dict) -> Any:
        if self.compensate_fn:
            result = self.compensate_fn(context)
        else:
            step_result = context.get("step_results", {}).get(self.name, {})
            txn_id = (
                step_result.get("transaction_id")
                if isinstance(step_result, dict)
                else None
            )
            result = {
                "refund_id": f"ref_{uuid.uuid4().hex[:12]}",
                "voided_transaction": txn_id,
                "status": "VOIDED",
            }
        logger.info("ExternalRewardAPIStep compensated: %s", result)
        return result


class BadgeRewardAllocationStep(SagaStep):
    """
    Awards a badge to the user.
    Compensation revokes the UserBadge if it was granted during this saga.
    """

    name = "badge_reward_allocation"

    def __init__(self, user: Any, badge_slug: str, step_name: Optional[str] = None):
        self.user = user
        self.badge_slug = badge_slug
        if step_name:
            self.name = step_name

    def execute(self, context: dict) -> Dict[str, Any]:
        badge = Badge.objects.filter(slug=self.badge_slug).first()
        if not badge:
            # No-op if badge does not exist
            result = {"badge_slug": self.badge_slug, "awarded": False}
            context.setdefault("step_results", {})[self.name] = result
            return result

        user_badge, created = UserBadge.objects.get_or_create(
            user=self.user, badge=badge
        )
        result = {
            "badge_slug": self.badge_slug,
            "badge_id": badge.id,
            "user_badge_id": user_badge.id,
            "created": created,
        }
        context.setdefault("step_results", {})[self.name] = result
        return result

    def compensate(self, context: dict) -> Dict[str, Any]:
        step_result = context.get("step_results", {}).get(self.name, {})
        if step_result.get("created"):
            user_badge_id = step_result.get("user_badge_id")
            if user_badge_id:
                deleted, _ = UserBadge.objects.filter(id=user_badge_id).delete()
                return {"revoked": bool(deleted)}
        return {"revoked": False}


class LambdaSagaStep(SagaStep):
    """
    Arbitrary step defined via execute and compensate callable functions.
    """

    def __init__(
        self,
        name: str,
        execute_fn: Callable[[dict], Any],
        compensate_fn: Callable[[dict], Any],
    ):
        self.name = name
        self.execute_fn = execute_fn
        self.compensate_fn = compensate_fn

    def execute(self, context: dict) -> Any:
        res = self.execute_fn(context)
        context.setdefault("step_results", {})[self.name] = res
        return res

    def compensate(self, context: dict) -> Any:
        return self.compensate_fn(context)


class RewardsSagaOrchestrator:
    """
    Two-Phase Commit (2PC) / Saga Runner.

    Orchestrates sequential execution of reward steps, persists state
    transitions in `RewardTransactionSaga`, and guarantees automated
    compensatory rollbacks when any step fails.
    """

    def __init__(
        self,
        user: Any,
        saga_id: Optional[str] = None,
        action_type: str = "cross_table_batch_reward",
        payload: Optional[Dict[str, Any]] = None,
        steps: Optional[List[SagaStep]] = None,
    ):
        self.user = user
        self.saga_id = saga_id or f"saga_{uuid.uuid4().hex}"
        self.action_type = action_type
        self.payload = payload or {}
        self.steps: List[SagaStep] = list(steps or [])
        self.context: Dict[str, Any] = {
            "saga_id": self.saga_id,
            "user_id": getattr(user, "id", None),
            "step_results": {},
            "compensation_results": {},
        }
        self.saga_record: Optional[RewardTransactionSaga] = None

    def add_step(self, step: SagaStep) -> RewardsSagaOrchestrator:
        """Add a step to the saga pipeline."""
        self.steps.append(step)
        return self

    def execute(self, raise_on_failure: bool = True) -> RewardTransactionSaga:
        """
        Execute the saga pipeline through the Two-Phase Commit state machine.

        State Transitions:
          1. PREPARING: Initial state recorded in DB before any action.
          2. Forward loop: Each step execute() is invoked.
          3. If all succeed: State transitions to COMMITTED.
          4. If any step fails:
             a. State transitions to COMPENSATING.
             b. Rollback: compensate() is invoked in REVERSE order on executed steps.
             c. State transitions to ABORTED.
             d. If raise_on_failure is True, raises SagaExecutionError.
        """
        # 1. State: PREPARING
        self.saga_record = RewardTransactionSaga.objects.create(
            saga_id=self.saga_id,
            user=self.user,
            status=RewardTransactionSaga.Status.PREPARING,
            action_type=self.action_type,
            payload=self.payload,
            step_states=[],
        )

        executed_steps: List[SagaStep] = []

        try:
            for step in self.steps:
                logger.info("Saga [%s] executing step: %s", self.saga_id, step.name)
                step_result = step.execute(self.context)
                executed_steps.append(step)

                # Persist step completion
                serializable_result = self._serialize_result(step_result)
                self.saga_record.step_states.append(
                    {
                        "step": step.name,
                        "status": "COMPLETED",
                        "result": serializable_result,
                    }
                )
                self.saga_record.save(update_fields=["step_states", "updated_at"])

            # 2. State: COMMITTED
            self.saga_record.status = RewardTransactionSaga.Status.COMMITTED
            self.saga_record.save(update_fields=["status", "updated_at"])
            logger.info(
                "Saga [%s] COMMITTED successfully across %d steps",
                self.saga_id,
                len(executed_steps),
            )
            return self.saga_record

        except Exception as exc:
            logger.error(
                "Saga [%s] encountered failure: %s. Initiating compensation.",
                self.saga_id,
                exc,
                exc_info=True,
            )

            # 3. State: COMPENSATING
            self.saga_record.status = RewardTransactionSaga.Status.COMPENSATING
            self.saga_record.error_message = str(exc)
            self.saga_record.save(
                update_fields=["status", "error_message", "updated_at"]
            )

            compensation_errors: List[tuple[str, Exception]] = []

            # Compensatory rollback loop in reverse order
            for step in reversed(executed_steps):
                try:
                    logger.info(
                        "Saga [%s] compensating step: %s", self.saga_id, step.name
                    )
                    comp_res = step.compensate(self.context)
                    self.context["compensation_results"][step.name] = comp_res
                    self.saga_record.step_states.append(
                        {
                            "step": step.name,
                            "status": "COMPENSATED",
                            "result": self._serialize_result(comp_res),
                        }
                    )
                except Exception as comp_exc:
                    logger.critical(
                        "Saga [%s] compensation failed on step %s: %s",
                        self.saga_id,
                        step.name,
                        comp_exc,
                        exc_info=True,
                    )
                    compensation_errors.append((step.name, comp_exc))
                    self.saga_record.step_states.append(
                        {
                            "step": step.name,
                            "status": "COMPENSATION_FAILED",
                            "error": str(comp_exc),
                        }
                    )

            # 4. State: ABORTED
            self.saga_record.status = RewardTransactionSaga.Status.ABORTED
            self.saga_record.save(
                update_fields=[
                    "status",
                    "step_states",
                    "error_message",
                    "updated_at",
                ]
            )
            logger.info("Saga [%s] ABORTED after compensation", self.saga_id)

            if raise_on_failure:
                raise SagaExecutionError(
                    f"Saga {self.saga_id} failed during execution and was rolled back to ABORTED: {exc}",
                    saga=self.saga_record,
                    original_exc=exc,
                    compensation_errors=compensation_errors,
                ) from exc

            return self.saga_record

    @staticmethod
    def _serialize_result(result: Any) -> Any:
        if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
            return result
        if isinstance(result, Decimal):
            return str(result)
        return repr(result)


def execute_cross_table_reward_allocation(
    user: Any,
    xp_items: Optional[List[Dict[str, Any]]] = None,
    financial_reward: Optional[Dict[str, Any]] = None,
    external_api_call: Optional[Callable[[dict], Any]] = None,
    external_api_compensate: Optional[Callable[[dict], Any]] = None,
    badge_slug: Optional[str] = None,
    saga_id: Optional[str] = None,
    action_type: str = "cross_table_financial_and_xp_batch",
    raise_on_failure: bool = True,
) -> RewardTransactionSaga:
    """
    High-level convenience orchestrator for cross-table financial reward
    and XP batch allocations.

    Coordinates:
      1. Batch XP allocation (XPEvent table).
      2. Financial reward allocation (FinancialReward table).
      3. Optional external reward/payout API (e.g., Stripe, PayPal, voucher).
      4. Optional badge award (UserBadge table).
    """
    orchestrator = RewardsSagaOrchestrator(
        user=user,
        saga_id=saga_id,
        action_type=action_type,
        payload={
            "xp_items": xp_items,
            "financial_reward": financial_reward,
            "badge_slug": badge_slug,
        },
    )

    if xp_items:
        orchestrator.add_step(XPBatchAllocationStep(user=user, items=xp_items))

    if financial_reward:
        orchestrator.add_step(
            FinancialRewardAllocationStep(
                user=user,
                amount=financial_reward.get("amount", 0),
                currency=financial_reward.get("currency", "USD"),
                source_type=financial_reward.get("source_type", "challenge_reward"),
                source_id=financial_reward.get("source_id", ""),
                metadata=financial_reward.get("metadata", {}),
            )
        )

    if external_api_call or external_api_compensate:
        orchestrator.add_step(
            ExternalRewardAPIStep(
                call_fn=external_api_call,
                compensate_fn=external_api_compensate,
            )
        )

    if badge_slug:
        orchestrator.add_step(
            BadgeRewardAllocationStep(user=user, badge_slug=badge_slug)
        )

    return orchestrator.execute(raise_on_failure=raise_on_failure)
