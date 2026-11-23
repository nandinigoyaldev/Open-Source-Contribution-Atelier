import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from apps.feature_flags.models import FeatureFlag, FeatureFlagAuditLog

logger = logging.getLogger(__name__)

# Typed loosely because Pyright cannot follow atomic() without django-stubs.
atomic: Any = transaction.atomic

# Fields that decide how a flag evaluates. Audit entries, rollback and the
# last-known cache all use this same list so they cannot drift apart.
EVALUATED_FIELDS = (
    "is_active",
    "flag_type",
    "rollout_percentage",
    "target_organizations",
    "target_users",
    "default_value",
    "environments",
    "kill_switch",
)

LAST_KNOWN_CACHE_KEY = "feature_flags:last_known:{name}"


def flag_snapshot(flag: FeatureFlag, include_name: bool = False) -> Dict[str, Any]:
    """The evaluation-relevant state of ``flag`` as plain JSON values."""
    snapshot: Dict[str, Any] = {}
    for field in EVALUATED_FIELDS:
        value = getattr(flag, field)
        snapshot[field] = list(value) if isinstance(value, (list, tuple)) else value
    if include_name:
        snapshot = {"name": flag.name, **snapshot}
    return snapshot


def current_environment() -> str:
    """Name of the environment this process runs in (``FEATURE_FLAG_ENVIRONMENT``)."""
    env = getattr(settings, "FEATURE_FLAG_ENVIRONMENT", "") or getattr(
        settings, "DJANGO_ENV", ""
    )
    return str(env or "development").strip().lower()


def normalize_environments(values: Any) -> List[str]:
    """Lower-case, strip and de-duplicate environment names, keeping order."""
    seen: List[str] = []
    for value in values or []:
        name = str(value).strip().lower()
        if name and name not in seen:
            seen.append(name)
    return seen


def compute_deterministic_bucket(key: str, salt: str = "") -> int:
    """
    Computes a deterministic bucket integer between 0 and 99 using SHA-256.
    Ensures stable percentage rollout evaluation for a given key and flag salt.
    """
    raw = f"{salt}:{key}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) % 100


def evaluate_feature_flag(
    flag: FeatureFlag, user=None, organization=None, environment=None
) -> Tuple[bool, str]:
    """
    Evaluates whether a feature flag is enabled for the provided context.
    Returns (is_enabled, evaluation_reason).

    ``environment`` defaults to :func:`current_environment`. The kill switch
    wins over everything else, including ``default_value``.
    """
    if flag.kill_switch:
        return False, "kill_switch_engaged"

    if not flag.is_active:
        return flag.default_value, "flag_inactive"

    scoped_envs = normalize_environments(flag.environments)
    env = (environment or current_environment()).strip().lower()
    if scoped_envs and env not in scoped_envs:
        return bool(flag.default_value), f"environment_out_of_scope ({env})"

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
            getattr(user, "username", None) or getattr(user, "id", None) or user
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
            return (
                True,
                f"percentage_included (bucket={bucket} < {flag.rollout_percentage})",
            )
        else:
            return (
                False,
                f"percentage_excluded (bucket={bucket} >= {flag.rollout_percentage})",
            )

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
    history = FeatureFlagAuditLog.objects.filter(flag=flag)
    if target_audit_id:
        target_log = history.filter(id=target_audit_id).first()
    else:
        target_log = (
            history.exclude(action="rolled_back").order_by("-timestamp").first()
        )

    if not target_log:
        raise ValueError(f"No previous audit history found for flag '{flag.name}'")

    target_values = target_log.old_values or target_log.new_values

    with atomic():
        current_values = flag_snapshot(flag)

        for key, val in target_values.items():
            if key in EVALUATED_FIELDS:
                setattr(flag, key, val)
        flag.save()

        audit = record_flag_change(
            flag=flag,
            actor=actor,
            action="rolled_back",
            scope="rollback",
            old_values=current_values,
            new_values=flag_snapshot(flag),
            reason=reason or f"Rolled back to audit log #{target_log.id}",
        )
    remember_flag_state(flag)
    return audit


def set_kill_switch(
    flag: FeatureFlag, engaged: bool, actor=None, reason: str = ""
) -> Optional[FeatureFlagAuditLog]:
    """
    Engage or release the emergency kill switch for ``flag``.

    The change and its audit entry are written in one transaction and the
    last-known cache is updated right away, so a later database outage still
    serves the flag as off. Returns ``None`` when the switch was already in the
    requested state (pressing it twice in an incident is not an error).
    """
    with atomic():
        locked = FeatureFlag.objects.select_for_update().get(pk=flag.pk)
        if locked.kill_switch == engaged:
            return None
        before = flag_snapshot(locked)
        locked.kill_switch = engaged
        locked.save(update_fields=["kill_switch", "updated_at"])
        audit = record_flag_change(
            flag=locked,
            actor=actor,
            action="kill_switch_engaged" if engaged else "kill_switch_released",
            scope="emergency",
            old_values=before,
            new_values=flag_snapshot(locked),
            reason=reason
            or ("Emergency disable" if engaged else "Kill switch released"),
        )
    remember_flag_state(locked)
    return audit


def remember_flag_state(flag: FeatureFlag) -> None:
    """Store ``flag``'s evaluated state as the last-known value (best effort)."""
    try:
        key = LAST_KNOWN_CACHE_KEY.format(name=flag.name)
        snapshot = flag_snapshot(flag)
        if cache.get(key) != snapshot:
            cache.set(key, snapshot, timeout=None)
    except Exception:  # the cache is optional here, never fail the caller
        logger.warning("Could not cache last-known state of flag %s", flag.name)


def forget_flag_state(name: str) -> None:
    try:
        cache.delete(LAST_KNOWN_CACHE_KEY.format(name=name))
    except Exception:
        logger.warning("Could not drop last-known state of flag %s", name)


def last_known_flag(name: str) -> Optional[FeatureFlag]:
    """
    An unsaved FeatureFlag rebuilt from the last-known cache, or ``None``.

    Used when the flag table cannot be read: evaluating the cached state keeps
    percentage buckets and targeting deterministic during the outage.
    """
    try:
        snapshot = cache.get(LAST_KNOWN_CACHE_KEY.format(name=name))
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    fields = {k: v for k, v in snapshot.items() if k in EVALUATED_FIELDS}
    return FeatureFlag(name=name, **fields)
