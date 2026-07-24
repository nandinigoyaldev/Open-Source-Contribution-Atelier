import uuid


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
