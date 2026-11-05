import datetime
import uuid
from decimal import Decimal

from .models import Invoice, Payment, SubscriptionPlan

ENTITLED_STATUSES = ("active", "trialing")


def from_stripe_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


def _first_item(subscription):
    items = subscription.get("items") or {}
    return (items.get("data") or [{}])[0]


def subscription_period_end(subscription):
    """
    Current period end of a Stripe subscription dict. Newer API versions moved
    current_period_end from the subscription onto its items.
    """
    timestamp = subscription.get("current_period_end") or _first_item(subscription).get(
        "current_period_end"
    )
    return from_stripe_timestamp(timestamp) if timestamp else None


def subscription_state(subscription):
    """
    The CustomerSubscription fields a Stripe subscription dict decides. The webhook
    applies these and reconcile_billing compares against them, so both agree.
    """
    status = subscription.get("status")
    state = {"status": status, "active": status in ENTITLED_STATUSES}

    period_end = subscription_period_end(subscription)
    if period_end:
        state["current_period_end"] = period_end

    price_id = (_first_item(subscription).get("price") or {}).get("id")
    if price_id:
        plan = SubscriptionPlan._default_manager.filter(
            stripe_price_id=price_id
        ).first()
        if plan:
            state["plan"] = plan

    if status == "active":
        state["payment_failed_at"] = None
    return state


def record_paid_invoice(sub, invoice):
    """
    Save a paid Stripe invoice dict for the subscription's user. A row left "open"
    by a failed attempt is settled. Returns the Invoice id when this call is what
    made it paid, so the caller can queue the PDF after commit, else None.
    """
    invoice_id = invoice.get("id")
    amount_paid = Decimal(invoice.get("amount_paid", 0)) / 100
    currency = invoice.get("currency", "usd").upper()
    charge_id = invoice.get("charge")

    invoice_obj, created = Invoice._default_manager.get_or_create(
        stripe_invoice_id=invoice_id,
        defaults={"user": sub.user, "amount": amount_paid, "status": "paid"},
    )
    if not created:
        if invoice_obj.status == "paid":
            return None
        invoice_obj.status = "paid"
        invoice_obj.amount = amount_paid
        invoice_obj.save(update_fields=["status", "amount"])

    Payment._default_manager.get_or_create(
        stripe_charge_id=charge_id or f"ch_mock_{invoice_id}",
        defaults={
            "user": sub.user,
            "amount": amount_paid,
            "currency": currency,
            "status": "succeeded",
        },
    )
    return invoice_obj.pk


def payout_bounty(user, bounty):
    """
    Simulates a Stripe Connect transfer to the user's account upon challenge completion.
    In a real application, this would use stripe.Transfer.create(...)
    """
    from .models import BountyClaim

    # Check if a claim already exists
    claim, created = BountyClaim.objects.get_or_create(
        bounty=bounty, user=user, defaults={"is_approved": True}
    )

    if not created and claim.is_approved:
        # Already paid out
        return claim

    claim.is_approved = True
    claim.payout_id = f"pi_mock_{uuid.uuid4().hex[:16]}"
    claim.save()

    # Deduct amount from sponsor or mark bounty as fulfilled based on logic
    bounty.is_active = False
    bounty.save()

    return claim
