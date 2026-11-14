"""
Account deletion service with retention policy, dependency checks, and grace period management.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)
User = get_user_model()

DEFAULT_GRACE_PERIOD_DAYS = 7


def get_retention_exceptions() -> List[Dict[str, str]]:
    """
    Documented retention policy exceptions.
    Records that must be retained for security, legal, or compliance purposes.
    """
    return [
        {
            "category": "security_audit",
            "record_type": "Audit events & access logs",
            "retention_period": "365 days",
            "reason": (
                "Retained for security compliance and incident investigation. "
                "Personal actor identifiers are detached/anonymized."
            ),
        },
        {
            "category": "financial_records",
            "record_type": "Invoices and payment ledger",
            "retention_period": "7 years",
            "reason": (
                "Retained to comply with statutory accounting and tax regulations. "
                "Billing profiles are detached from personal user records."
            ),
        },
    ]


def get_erasable_scope() -> List[str]:
    """
    List of personal data records that will be permanently erased.
    """
    return [
        "Personal user profile, bio, avatars, and linked social profiles",
        "Private lesson notes and encrypted notebook data",
        "Learning journal reflections and personal goals",
        "Lesson progress records, quizzes, streaks, and certificates",
        "Authentication credentials, active sessions, and API tokens",
        "Personal notifications and preferences",
    ]


def check_blocking_dependencies(user) -> List[Dict[str, Any]]:
    """
    Check for blocking dependencies that prevent account deletion, such as:
    1. Sole ownership of an active organization.
    2. Active billing subscription.
    """
    blocking = []

    # 1. Organization ownership check
    try:
        from apps.organizations.models import OrganizationMembership

        owned_memberships = OrganizationMembership.objects.filter(
            user=user, role=OrganizationMembership.ROLE_OWNER
        ).select_related("organization")

        for m in owned_memberships:
            other_owners = OrganizationMembership.objects.filter(
                organization=m.organization, role=OrganizationMembership.ROLE_OWNER
            ).exclude(user=user)

            if not other_owners.exists():
                blocking.append(
                    {
                        "type": "organization_sole_owner",
                        "entity_id": m.organization.id,
                        "entity_name": m.organization.name,
                        "message": (
                            f"You are the sole owner of organization '{m.organization.name}'. "
                            "Transfer ownership to another member or delete the organization first."
                        ),
                    }
                )
    except Exception as e:
        logger.debug(f"Organization dependency check error: {e}")

    # 2. Billing subscription check
    try:
        from apps.billing.models import CustomerSubscription

        sub = CustomerSubscription.objects.filter(user=user).first()
        if sub and (sub.active or sub.status in ("active", "trialing")):
            plan_name = getattr(sub.plan, "name", "Active Subscription")
            blocking.append(
                {
                    "type": "active_subscription",
                    "entity_id": sub.id,
                    "entity_name": plan_name,
                    "message": (
                        f"You have an active subscription ({plan_name}). "
                        "Please cancel your subscription before deleting your account."
                    ),
                }
            )
    except Exception as e:
        logger.debug(f"Billing dependency check error: {e}")

    return blocking


def get_deletion_preview(user) -> Dict[str, Any]:
    """
    Generate preview showing blocking dependencies, retention exceptions, and erasable items.
    """
    blocking = check_blocking_dependencies(user)
    from apps.accounts.models import AccountDeletionRequest

    pending = (
        AccountDeletionRequest.objects.filter(
            user=user, status=AccountDeletionRequest.STATUS_PENDING
        )
        .order_by("-requested_at")
        .first()
    )

    pending_data = None
    if pending:
        pending_data = {
            "id": str(pending.id),
            "status": pending.status,
            "requested_at": pending.requested_at.isoformat(),
            "scheduled_for": pending.scheduled_for.isoformat(),
            "reason": pending.reason,
        }

    return {
        "can_delete": len(blocking) == 0,
        "blocking_dependencies": blocking,
        "retention_exceptions": get_retention_exceptions(),
        "erasable_scope": get_erasable_scope(),
        "grace_period_days": DEFAULT_GRACE_PERIOD_DAYS,
        "pending_request": pending_data,
    }


def schedule_account_deletion(
    user, reason: str = "", grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
):
    """
    Schedule account deletion after a grace period.
    """
    blocking = check_blocking_dependencies(user)
    if blocking:
        raise ValidationError(
            {
                "error": "Account deletion blocked by existing dependencies.",
                "blocking_dependencies": blocking,
            }
        )

    from apps.accounts.models import AccountDeletionRequest

    # Cancel any existing pending requests
    AccountDeletionRequest.objects.filter(
        user=user, status=AccountDeletionRequest.STATUS_PENDING
    ).update(status=AccountDeletionRequest.STATUS_CANCELLED)

    scheduled_for = timezone.now() + timedelta(days=grace_period_days)
    deletion_request = AccountDeletionRequest.objects.create(
        user=user,
        status=AccountDeletionRequest.STATUS_PENDING,
        scheduled_for=scheduled_for,
        reason=reason,
    )
    return deletion_request


def cancel_account_deletion(user) -> bool:
    """
    Cancel an in-progress account deletion request during the grace period.
    """
    from apps.accounts.models import AccountDeletionRequest

    updated = AccountDeletionRequest.objects.filter(
        user=user, status=AccountDeletionRequest.STATUS_PENDING
    ).update(status=AccountDeletionRequest.STATUS_CANCELLED)

    return updated > 0


@transaction.atomic
def execute_account_deletion(user):
    """
    Idempotent and resumable account deletion.
    Anonymizes public contributions, severs audit/financial dependencies,
    and removes personal identifiers and account records.
    """
    if not user or not user.pk:
        return

    # Check blocking dependencies
    blocking = check_blocking_dependencies(user)
    if blocking:
        raise ValidationError(
            {
                "error": "Account deletion blocked by existing dependencies.",
                "blocking_dependencies": blocking,
            }
        )

    # 1. Fetch or create Anonymous user for public contributions
    anonymous_user, _ = User.objects.get_or_create(
        username="anonymous_contributor",
        defaults={
            "email": "anonymous@example.com",
            "first_name": "Anonymous",
            "last_name": "Contributor",
            "is_active": False,
        },
    )
    if anonymous_user.password == "":
        anonymous_user.set_unusable_password()
        anonymous_user.save()

    # 2. Re-assign public contributions to preserve community context without PII
    try:
        from apps.content.models import Comment

        Comment.objects.filter(user=user).update(user=anonymous_user)
    except Exception:
        pass

    try:
        from apps.chat.models import Message

        Message.objects.filter(user=user).update(user=anonymous_user)
    except Exception:
        pass

    # 3. Handle Audit Events (retain audit records with severed actor per retention policy)
    try:
        from apps.audit.models import AuditEvent

        AuditEvent.objects.filter(actor=user).update(actor=None)
    except Exception:
        pass

    # 4. Mark deletion requests as completed
    try:
        from apps.accounts.models import AccountDeletionRequest

        AccountDeletionRequest.objects.filter(
            user=user, status=AccountDeletionRequest.STATUS_PENDING
        ).update(
            status=AccountDeletionRequest.STATUS_COMPLETED,
            completed_at=timezone.now(),
        )
    except Exception:
        pass

    # 5. Delete the user (cascades profile, notes, progress, certificates, tokens)
    user.delete()
