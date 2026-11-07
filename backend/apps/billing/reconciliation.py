"""
Compare local billing state with Stripe and repair what drifted.

Stripe is the source of truth. A run only reads unless ``apply`` is set, and either
way it leaves one audit event with what it found, so a dry run can be checked
against the repairs that follow it. See docs/STRIPE_WEBHOOK_LEDGER.md.
"""

import dataclasses
import datetime
import logging
import types
import uuid
from decimal import Decimal
from functools import partial
from typing import Any, Callable, Dict, List, Optional

import stripe
from django.db import models, transaction
from django.utils import timezone

from apps.audit.admin_events import (
    BILLING_RECONCILE_REPAIR,
    BILLING_RECONCILE_RUN,
    record_admin_event,
    target_type_for,
)
from apps.audit.models import AuditEvent
from config.db_router import use_primary

from .models import CustomerSubscription, Invoice, StripeEvent
from .services import ENTITLED_STATUSES, record_paid_invoice, subscription_state
from .webhooks import queue_invoice_pdf

logger = logging.getLogger(__name__)

SUBSCRIPTION_STATE = "subscription_state"
SUBSCRIPTION_MISSING = "subscription_missing"
INVOICE_MISSING = "invoice_missing"
INVOICE_STATUS = "invoice_status"
EVENT_UNMATCHED = "event_unmatched"

# Keeps the audit row small. The counts still cover everything.
MAX_AUDITED_MISMATCHES = 200
MAX_UNMATCHED_EVENTS = 500

# Typed loosely because Pyright cannot follow atomic() without django-stubs.
atomic: Any = transaction.atomic


class StripeClient:
    """Everything reconcile asks Stripe, as plain dicts. Tests swap this for a fake."""

    def subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        try:
            return stripe.Subscription.retrieve(subscription_id).to_dict()
        except stripe.InvalidRequestError as exc:
            if exc.code == "resource_missing":
                return None
            raise

    def customer_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        found = stripe.Subscription.list(customer=customer_id, status="all", limit=100)
        return [item.to_dict() for item in found.auto_paging_iter()]

    def invoices(
        self, customer_id: str, since: datetime.datetime
    ) -> List[Dict[str, Any]]:
        found = stripe.Invoice.list(
            customer=customer_id, created={"gte": int(since.timestamp())}, limit=100
        )
        return [item.to_dict() for item in found.auto_paging_iter()]


class AuditWriteError(Exception):
    """Raised inside a repair so it rolls back instead of going unaudited."""


@dataclasses.dataclass
class Mismatch:
    kind: str
    customer_id: str
    stripe_id: str
    detail: Dict[str, Any]
    repairable: bool = True
    repaired: bool = False
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, models.Model):
        return str(value)
    return value


def _change(local: Any, remote: Any) -> Dict[str, Any]:
    return {"local": _json_safe(local), "stripe": _json_safe(remote)}


def subscription_diff(sub: Any, remote: Dict[str, Any]) -> Dict[str, Any]:
    diff = {}
    if sub.stripe_subscription_id != remote.get("id"):
        diff["stripe_subscription_id"] = _change(
            sub.stripe_subscription_id, remote.get("id")
        )
    for field, value in subscription_state(remote).items():
        local = getattr(sub, field)
        if local != value:
            diff[field] = _change(local, value)
    return diff


class Reconciler:
    def __init__(
        self,
        client: Any,
        *,
        apply: bool = False,
        days: int = 30,
        customer: Optional[str] = None,
    ):
        self.client = client
        self.apply = apply
        self.days = days
        self.customer = customer
        self.since = timezone.now() - datetime.timedelta(days=days)
        self.run_id = str(uuid.uuid4())
        self.checked = 0
        self.mismatches: List[Mismatch] = []
        self.errors: List[Dict[str, str]] = []

    def run(self) -> "Reconciler":
        # The comparison has to see the primary, a lagging replica would report
        # drift that is not there.
        with use_primary():
            for sub in self._rows():
                self.checked += 1
                try:
                    self._check_subscription(sub)
                    self._check_invoices(sub)
                except Exception as exc:
                    self._error(sub.stripe_customer_id, exc)
            self._check_unmatched_events()
        self._audit_run()
        return self

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dry_run": not self.apply,
            "days": self.days,
            "customer": self.customer,
            "checked": self.checked,
            "mismatches": len(self.mismatches),
            "repaired": sum(1 for item in self.mismatches if item.repaired),
            "manual": sum(1 for item in self.mismatches if not item.repairable),
            "errors": len(self.errors),
        }

    def as_dict(self) -> Dict[str, Any]:
        report = self.summary()
        report["mismatches"] = [item.as_dict() for item in self.mismatches]
        report["errors"] = self.errors
        return report

    def _rows(self) -> List[Any]:
        rows = (
            CustomerSubscription._default_manager.select_related("plan", "user")
            .exclude(stripe_customer_id="")
            .exclude(stripe_customer_id__startswith="cus_mock_")
            .order_by("pk")
        )
        if self.customer:
            rows = rows.filter(stripe_customer_id=self.customer)
        return list(rows)

    def _error(self, customer_id: str, exc: Exception) -> None:
        logger.warning("Reconcile failed for %s: %s", customer_id, exc)
        self.errors.append({"customer_id": customer_id, "error": str(exc)})

    def _found(self, mismatch: Mismatch, repair: Optional[Callable] = None) -> None:
        self.mismatches.append(mismatch)
        if not self.apply or repair is None:
            return
        try:
            mismatch.repaired = repair()
        except Exception as exc:
            self._error(mismatch.customer_id, exc)
            return
        if not mismatch.repaired:
            mismatch.note = "skipped, a newer event landed during the run"

    def _audit(
        self, target: Any, action: str, mismatch: Mismatch, summary: str
    ) -> None:
        payload = {
            "run_id": self.run_id,
            "kind": mismatch.kind,
            "customer_id": mismatch.customer_id,
            "stripe_id": mismatch.stripe_id,
            "detail": mismatch.detail,
        }
        event = record_admin_event(
            operation=BILLING_RECONCILE_REPAIR,
            action=action,
            target_type=target_type_for(target),
            target_id=target.pk,
            request=types.SimpleNamespace(request_id=self.run_id),
            payload=payload,
            summary=summary,
        )
        if event is None:
            raise AuditWriteError(f"no audit event for {mismatch.stripe_id}")

    def _audit_run(self) -> None:
        report = self.as_dict()
        report["mismatch_count"] = len(self.mismatches)
        report["mismatches"] = report["mismatches"][:MAX_AUDITED_MISMATCHES]
        mode = "dry run" if not self.apply else "apply"
        event = record_admin_event(
            operation=BILLING_RECONCILE_RUN,
            action=AuditEvent.ACTION_CREATED,
            target_type="billing.reconciliation",
            target_id=self.run_id,
            request=types.SimpleNamespace(request_id=self.run_id),
            payload=report,
            summary=f"Billing reconcile {mode}: {len(self.mismatches)} mismatches",
        )
        if event is None:
            self.errors.append(
                {"customer_id": "", "error": "could not write the run audit event"}
            )

    def _remote_subscription(self, sub: Any) -> Optional[Dict[str, Any]]:
        """
        The Stripe subscription this row should follow: the one it is bound to,
        unless that one is over and the customer has a live one, which means a
        checkout event never arrived.
        """
        bound = None
        if sub.stripe_subscription_id:
            bound = self.client.subscription(sub.stripe_subscription_id)
        if bound is not None and bound.get("status") in ENTITLED_STATUSES:
            return bound
        live = [
            item
            for item in self.client.customer_subscriptions(sub.stripe_customer_id)
            if item.get("status") in ENTITLED_STATUSES
        ]
        if live:
            return max(live, key=lambda item: item.get("created", 0))
        return bound

    def _check_subscription(self, sub: Any) -> None:
        fetched_at = timezone.now()
        remote = self._remote_subscription(sub)
        if remote is None:
            if sub.stripe_subscription_id:
                # Stripe keeps canceled subscriptions, so this is a wrong id or a
                # key from the wrong account. Too risky to revoke access on that.
                self._found(
                    Mismatch(
                        kind=SUBSCRIPTION_MISSING,
                        customer_id=sub.stripe_customer_id,
                        stripe_id=sub.stripe_subscription_id,
                        detail={"active": sub.active, "status": sub.status},
                        repairable=False,
                    )
                )
            return

        diff = subscription_diff(sub, remote)
        if not diff:
            return
        mismatch = Mismatch(
            kind=SUBSCRIPTION_STATE,
            customer_id=sub.stripe_customer_id,
            stripe_id=remote["id"],
            detail=diff,
        )
        self._found(
            mismatch,
            partial(self._repair_subscription, sub.pk, remote, fetched_at, mismatch),
        )

    @atomic
    def _repair_subscription(
        self,
        pk: int,
        remote: Dict[str, Any],
        fetched_at: datetime.datetime,
        mismatch: Mismatch,
    ) -> bool:
        sub = CustomerSubscription._default_manager.select_for_update().get(pk=pk)
        if sub.last_event_at and sub.last_event_at > fetched_at:
            return False
        sub.stripe_subscription_id = remote["id"]
        for field, value in subscription_state(remote).items():
            setattr(sub, field, value)
        # Events older than this fetch that land later are now stale, so they
        # cannot undo the repair.
        sub.last_event_at = fetched_at
        sub.save()
        self._audit(
            sub,
            AuditEvent.ACTION_UPDATED,
            mismatch,
            f"Reconcile repaired subscription row #{sub.pk}",
        )
        return True

    def _check_invoices(self, sub: Any) -> None:
        remote_invoices = self.client.invoices(sub.stripe_customer_id, self.since)
        local_invoices = {
            item.stripe_invoice_id: item
            for item in Invoice._default_manager.filter(
                stripe_invoice_id__in=[item.get("id") for item in remote_invoices]
            )
        }
        for remote in remote_invoices:
            status = remote.get("status")
            local = local_invoices.get(remote.get("id"))
            if local is None and status != "paid":
                continue
            if local is not None and local.status == status:
                continue

            mismatch = Mismatch(
                kind=INVOICE_MISSING if local is None else INVOICE_STATUS,
                customer_id=sub.stripe_customer_id,
                stripe_id=remote["id"],
                detail={"status": _change(local and local.status, status)},
                repairable=local is not None or sub.user is not None,
            )
            repair = None
            if mismatch.repairable:
                repair = partial(self._repair_invoice, sub, remote, mismatch)
            self._found(mismatch, repair)

    def _repair_invoice(
        self, sub: Any, remote: Dict[str, Any], mismatch: Mismatch
    ) -> bool:
        pdf_invoice_id = self._write_invoice_repair(sub, remote, mismatch)
        if pdf_invoice_id:
            queue_invoice_pdf(pdf_invoice_id)
        return True

    @atomic
    def _write_invoice_repair(
        self, sub: Any, remote: Dict[str, Any], mismatch: Mismatch
    ) -> Optional[int]:
        pdf_invoice_id = None
        if remote.get("status") == "paid":
            pdf_invoice_id = record_paid_invoice(sub, remote)
            invoice = Invoice._default_manager.get(stripe_invoice_id=remote["id"])
        else:
            invoice = Invoice._default_manager.select_for_update().get(
                stripe_invoice_id=remote["id"]
            )
            invoice.status = remote.get("status")
            invoice.save(update_fields=["status"])
        self._audit(
            invoice,
            (
                AuditEvent.ACTION_CREATED
                if mismatch.kind == INVOICE_MISSING
                else AuditEvent.ACTION_UPDATED
            ),
            mismatch,
            f"Reconcile repaired invoice row #{invoice.pk}",
        )
        return pdf_invoice_id

    def _check_unmatched_events(self) -> None:
        """Events for a customer we have no row for: nothing local can fix these."""
        known = CustomerSubscription._default_manager.values("stripe_customer_id")
        events = StripeEvent._default_manager.filter(
            outcome=StripeEvent.OUTCOME_UNMATCHED, event_created_at__gte=self.since
        ).exclude(customer_id__in=known)
        if self.customer:
            events = events.filter(customer_id=self.customer)
        for event in events.order_by("event_created_at")[:MAX_UNMATCHED_EVENTS]:
            self._found(
                Mismatch(
                    kind=EVENT_UNMATCHED,
                    customer_id=event.customer_id,
                    stripe_id=event.event_id,
                    detail={
                        "event_type": event.event_type,
                        "object_id": event.object_id,
                        "event_created_at": _json_safe(event.event_created_at),
                    },
                    repairable=False,
                )
            )
