import logging
import time
import uuid

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django_q.tasks import async_task

from .models import (
    CustomerSubscription,
    Invoice,
    Payment,
    StripeEvent,
    SubscriptionPlan,
)
from .services import (
    from_stripe_timestamp,
    record_paid_invoice,
    subscription_period_end,
    subscription_state,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def queue_invoice_pdf(invoice_id):
    """
    Call after commit, so a worker can always see the invoice. A lost task is not
    fatal: the download view builds a missing PDF on demand.
    """
    try:
        async_task("apps.billing.tasks.generate_invoice_pdf_task", invoice_id)
    except Exception:
        logger.exception("Could not queue PDF for invoice %s", invoice_id)


def _plain_object(obj):
    """Real Stripe objects have no .get(), mock ones are plain dicts already."""
    return obj.to_dict() if isinstance(obj, stripe.StripeObject) else obj


def _is_stale(sub, occurred_at):
    """True when the row already shows something newer than this event."""
    if sub.last_event_at is None:
        return False
    if occurred_at == sub.last_event_at:
        # created is in whole seconds, so a failed payment and the cancellation it
        # leads to can share one. A cancellation wins the tie.
        return sub.status == "canceled"
    return occurred_at < sub.last_event_at


def _locked_subscription(subscription_id, customer_id):
    """
    Row an event for this subscription belongs to, locked so two events for one
    subscription apply one at a time. A row that follows another live subscription
    does not take events for this one, those would overwrite the wrong state.
    """
    rows = CustomerSubscription._default_manager.select_for_update()
    sub = None
    if subscription_id:
        sub = rows.filter(stripe_subscription_id=subscription_id).first()
    if sub is None and customer_id:
        sub = rows.filter(stripe_customer_id=customer_id).first()
        if sub and sub.stripe_subscription_id and sub.status != "canceled":
            return None
    return sub


def _checkout_period_end(session, is_mock):
    """Runs before the transaction, so no row stays locked over a Stripe call."""
    subscription_id = session.get("subscription")
    if is_mock:
        return timezone.now() + timezone.timedelta(days=30)
    if not subscription_id:
        return None
    try:
        return subscription_period_end(
            stripe.Subscription.retrieve(subscription_id).to_dict()
        )
    except Exception as e:
        logger.warning("Caught exception: %s", e)
        return None


def _apply_checkout(session, occurred_at, period_end):
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id")
    plan_id = metadata.get("plan_id")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    user = None
    if user_id:
        user = User._default_manager.filter(id=user_id).first()
    if not user and customer_id:
        sub_profile = (
            CustomerSubscription._default_manager.select_related("user")
            .filter(stripe_customer_id=customer_id)
            .first()
        )
        if sub_profile:
            user = sub_profile.user
    if not user:
        return StripeEvent.OUTCOME_UNMATCHED

    plan = SubscriptionPlan._default_manager.filter(id=plan_id).first()
    sub, _ = CustomerSubscription._default_manager.select_for_update().get_or_create(
        user=user
    )

    bound_id = sub.stripe_subscription_id
    other_subscription = bool(bound_id) and bound_id != subscription_id
    # A purchase after the old subscription ended starts a new timeline, even if
    # its event was created just before the old subscription's last one.
    new_purchase = other_subscription and sub.status == "canceled"
    if _is_stale(sub, occurred_at) and not new_purchase:
        if not other_subscription:
            # Newer events already set the status, but only this one links the
            # user to the subscription. Fill the gaps and leave the state alone.
            sub.stripe_customer_id = sub.stripe_customer_id or customer_id
            sub.stripe_subscription_id = subscription_id
            sub.plan = sub.plan or plan
            sub.current_period_end = sub.current_period_end or period_end
            sub.save()
        return StripeEvent.OUTCOME_STALE

    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = subscription_id
    if plan:
        sub.plan = plan
    sub.active = True
    sub.status = "active"
    sub.payment_failed_at = None
    if period_end:
        sub.current_period_end = period_end
    sub.last_event_at = occurred_at
    sub.save()
    return StripeEvent.OUTCOME_APPLIED


def _apply_subscription_updated(subscription, occurred_at):
    sub_id = subscription.get("id")
    sub = _locked_subscription(sub_id, subscription.get("customer"))
    if sub is None:
        return StripeEvent.OUTCOME_UNMATCHED
    if _is_stale(sub, occurred_at):
        return StripeEvent.OUTCOME_STALE

    sub.stripe_subscription_id = sub_id
    for field, value in subscription_state(subscription).items():
        setattr(sub, field, value)
    sub.last_event_at = occurred_at
    sub.save()
    return StripeEvent.OUTCOME_APPLIED


def _apply_subscription_deleted(subscription, occurred_at):
    sub_id = subscription.get("id")
    sub = _locked_subscription(sub_id, subscription.get("customer"))
    if sub is None:
        return StripeEvent.OUTCOME_UNMATCHED
    if sub.stripe_subscription_id and sub.stripe_subscription_id != sub_id:
        # The row follows another subscription that has ended already.
        return StripeEvent.OUTCOME_STALE

    # No staleness check: Stripe never revives a canceled subscription, so this
    # holds however late it lands.
    sub.stripe_subscription_id = sub_id
    sub.active = False
    sub.status = "canceled"
    if sub.last_event_at is None or occurred_at > sub.last_event_at:
        sub.last_event_at = occurred_at
    sub.save()
    return StripeEvent.OUTCOME_APPLIED


def _apply_invoice_paid(invoice):
    """Returns the outcome and the id of an invoice that needs its PDF, if any."""
    sub = (
        CustomerSubscription._default_manager.select_related("user")
        .filter(stripe_customer_id=invoice.get("customer"))
        .first()
    )
    if not sub or not sub.user:
        return StripeEvent.OUTCOME_UNMATCHED, None
    return StripeEvent.OUTCOME_APPLIED, record_paid_invoice(sub, invoice)


def _apply_invoice_payment_failed(invoice, occurred_at):
    invoice_id = invoice.get("id")
    amount_due = invoice.get("amount_due", 0) / 100.0
    currency = invoice.get("currency", "usd").upper()

    sub = (
        CustomerSubscription._default_manager.select_for_update()
        .filter(stripe_customer_id=invoice.get("customer"))
        .first()
    )
    if not sub or not sub.user:
        return StripeEvent.OUTCOME_UNMATCHED

    outcome = StripeEvent.OUTCOME_STALE
    if not _is_stale(sub, occurred_at):
        sub.status = "past_due"
        sub.payment_failed_at = occurred_at
        sub.last_event_at = occurred_at
        sub.save()
        outcome = StripeEvent.OUTCOME_APPLIED

    # The failed attempt happened either way, so a late one is still written down.
    Invoice._default_manager.get_or_create(
        stripe_invoice_id=invoice_id,
        defaults={"user": sub.user, "amount": amount_due, "status": "open"},
    )
    Payment._default_manager.get_or_create(
        stripe_charge_id=f"ch_failed_{invoice_id}",
        defaults={
            "user": sub.user,
            "amount": amount_due,
            "currency": currency,
            "status": "failed",
        },
    )
    return outcome


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_mock")

    is_mock = getattr(settings, "TESTING", False) or stripe.api_key == "sk_test_mock"

    if not is_mock and sig_header is None:
        return HttpResponse("Missing Stripe-Signature header", status=400)

    if is_mock:
        try:
            import json

            event_data = json.loads(payload)

            class MockEvent:
                def __init__(self, data):
                    self.type = data.get("type")
                    # Without an id every mock event would look like one delivery.
                    self.id = data.get("id") or f"evt_mock_{uuid.uuid4().hex}"
                    self.created = int(data.get("created") or time.time())

                    class DataObj:
                        def __init__(self, obj):
                            self.object = obj

                    self.data = DataObj(data.get("data", {}).get("object", {}))

            event = MockEvent(event_data)
        except Exception as e:
            logger.warning("Caught exception: %s", e)
            return HttpResponse(status=400)
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)

    event_object = _plain_object(event.data.object)
    occurred_at = from_stripe_timestamp(event.created)

    period_end = None
    if event.type == "checkout.session.completed":
        period_end = _checkout_period_end(event_object, is_mock)

    pdf_invoice_id = None
    try:
        with transaction.atomic():
            customer_id = event_object.get("customer")
            ledger, is_new = StripeEvent._default_manager.get_or_create(
                event_id=event.id,
                defaults={
                    "event_type": event.type or "",
                    "object_id": event_object.get("id") or "",
                    "customer_id": customer_id if isinstance(customer_id, str) else "",
                    "event_created_at": occurred_at,
                },
            )
            if not is_new:
                logger.info("Skipping duplicate Stripe event %s", event.id)
                return HttpResponse(status=200)

            if event.type == "checkout.session.completed":
                ledger.outcome = _apply_checkout(event_object, occurred_at, period_end)
            elif event.type == "customer.subscription.updated":
                ledger.outcome = _apply_subscription_updated(event_object, occurred_at)
            elif event.type == "customer.subscription.deleted":
                ledger.outcome = _apply_subscription_deleted(event_object, occurred_at)
            elif event.type == "invoice.paid":
                ledger.outcome, pdf_invoice_id = _apply_invoice_paid(event_object)
            elif event.type == "invoice.payment_failed":
                ledger.outcome = _apply_invoice_payment_failed(
                    event_object, occurred_at
                )
            ledger.save(update_fields=["outcome"])
    except Exception:
        # The ledger row rolled back with the rest, so Stripe's retry starts clean.
        logger.exception("Stripe event %s (%s) failed", event.id, event.type)
        return HttpResponse(status=500)

    if pdf_invoice_id:
        queue_invoice_pdf(pdf_invoice_id)

    return HttpResponse(status=200)
