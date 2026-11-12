import hashlib
from typing import Any, Dict, Optional, Tuple

from apps.feature_flags.models import FeatureFlag, FeatureFlagAuditLog


def compute_deterministic_bucket(key: str, salt: str = "") -> int:
    """
    Computes a deterministic bucket integer between 0 and 99 using SHA-256.
    Ensures stable percentage rollout evaluation for a given key and flag salt.
    """
    raw = f"{salt}:{key}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) % 100


def evaluate_feature_flag(
    flag: FeatureFlag, user=None, organization=None
) -> Tuple[bool, str]:
    """
    Evaluates whether a feature flag is enabled for the provided context.
    Returns (is_enabled, evaluation_reason).
    """
    if not flag.is_active:
        return flag.default_value, "flag_inactive"

    # 1. Organization targeting check
    org_key = ""
    if organization is not None:
        org_key = str(
            getattr(organization, "slug", None)
            or getattr(organization, "id", None)
            or organization
        )

    if org_key and flag.target_organizations:
        allowed_orgs = [str(o) for o in flag.target_organizations]
        if org_key in allowed_orgs:
            return True, f"organization_targeted ({org_key})"
        elif flag.flag_type == "organization":
            return False, f"organization_not_in_targets ({org_key})"

    # 2. User targeting check
    user_key = ""
    if user is not None:
        user_key = str(
            getattr(user, "username", None)
            or getattr(user, "id", None)
            or user
        )

    if user_key and flag.target_users:
        allowed_users = [str(u) for u in flag.target_users]
        if user_key in allowed_users:
            return True, f"user_targeted ({user_key})"
        elif flag.flag_type == "user":
            return False, f"user_not_in_targets ({user_key})"

    # 3. Percentage rollout check
    if flag.flag_type == "percentage" or flag.rollout_percentage > 0:
        entity_key = user_key or org_key
        if not entity_key:
            return flag.default_value, "anonymous_fallback"

        bucket = compute_deterministic_bucket(entity_key, salt=flag.name)
        if bucket < flag.rollout_percentage:
            return True, f"percentage_included (bucket={bucket} < {flag.rollout_percentage})"
        else:
            return False, f"percentage_excluded (bucket={bucket} >= {flag.rollout_percentage})"

    # 4. Standard active boolean flag
    return True, "flag_active_global"


def record_flag_change(
    flag: FeatureFlag,
    actor=None,
    action: str = "updated",
    scope: str = "global",
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> FeatureFlagAuditLog:
    """
    Creates an immutable audit log entry for a flag mutation.
    """
    return FeatureFlagAuditLog.objects.create(
        flag=flag,
        actor=actor,
        action=action,
        scope=scope,
        old_values=old_values or {},
        new_values=new_values or {},
        reason=reason,
    )


def rollback_feature_flag(
    flag: FeatureFlag,
    actor=None,
    reason: str = "",
    target_audit_id: Optional[int] = None,
) -> FeatureFlagAuditLog:
    """
    Rolls back a feature flag to a previous configuration in ONE atomic action,
    preserving full audit history.
    """
    if target_audit_id:
        target_log = flag.audit_logs.filter(id=target_audit_id).first()
    else:
        target_log = (
            flag.audit_logs.exclude(action="rolled_back")
            .order_by("-timestamp")
            .first()
        )

    if not target_log:
        raise ValueError(f"No previous audit history found for flag '{flag.name}'")

    target_values = target_log.old_values or target_log.new_values

    current_values = {
        "is_active": flag.is_active,
        "flag_type": flag.flag_type,
        "rollout_percentage": flag.rollout_percentage,
        "target_organizations": flag.target_organizations,
        "target_users": flag.target_users,
        "default_value": flag.default_value,
    }

    for key, val in target_values.items():
        if hasattr(flag, key):
            setattr(flag, key, val)
    flag.save()

    return record_flag_change(
        flag=flag,
        actor=actor,
        action="rolled_back",
        scope="rollback",
        old_values=current_values,
        new_values=target_values,
        reason=reason or f"Rolled back to audit log #{target_log.id}",
    )
