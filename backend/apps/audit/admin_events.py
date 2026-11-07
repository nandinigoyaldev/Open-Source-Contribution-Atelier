"""
Structured audit events for admin actions.

One event shape, written through ``record_admin_event``:

    actor        who did it (``AuditEvent.actor``)
    operation    what was done, e.g. ``issue.updated`` (``extra["operation"]``)
    action       coarse verb: created / updated / deleted (``AuditEvent.action``)
    target_type  ``app_label.model_name`` of the thing acted on
    target_id    primary key of the target, as a string
    timestamp    ``AuditEvent.created_at``
    request_id   the ``X-Request-ID`` of the request (``AuditEvent.correlation_id``)
    payload      small, redacted dict of what changed (``extra["payload"]``)

The existing ``AuditEvent`` table is reused, so there is no new model and no
migration. ``action`` is a varchar(10) limited to the three verbs, which is why
the specific operation lives in ``extra``.

Recording an event must never break the admin action it describes, so
``record_admin_event`` catches everything and logs it.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import transaction

from apps.audit.middleware import get_audit_context
from apps.audit.models import AuditEvent
from apps.audit.redaction import redact, redact_string

logger = logging.getLogger(__name__)

# Operation names used by the admin actions that emit events.
ISSUE_UPDATED = "issue.updated"
ISSUE_DELETED = "issue.deleted"
USER_ROLE_ASSIGNED = "user.role_assigned"
USER_ROLE_REVOKED = "user.role_revoked"
BILLING_RECONCILE_RUN = "billing.reconcile_run"
BILLING_RECONCILE_REPAIR = "billing.reconcile_repair"

_VALID_ACTIONS = {
    AuditEvent.ACTION_CREATED,
    AuditEvent.ACTION_UPDATED,
    AuditEvent.ACTION_DELETED,
}
_MAX_REQUEST_ID_LENGTH = 64


def target_type_for(obj_or_model: Any) -> str:
    """``app_label.model_name`` for a model class or instance."""
    meta = obj_or_model._meta
    return f"{meta.app_label}.{meta.model_name}"


def _request_id(request: Any) -> str:
    request_id = getattr(request, "request_id", "") if request is not None else ""
    if not request_id:
        request_id = get_audit_context().get("correlation_id", "")
    return str(request_id or "")[:_MAX_REQUEST_ID_LENGTH]


def _actor(request: Any, actor: Any) -> Optional[Any]:
    if actor is None and request is not None:
        actor = getattr(request, "user", None)
    if actor is not None and getattr(actor, "is_authenticated", False):
        return actor
    return None


def write_event(
    *,
    action: str,
    target_type: str,
    target_id: Any,
    request_id: str,
    extra: dict,
    actor: Any = None,
    ip_address: Optional[str] = None,
    user_agent: str = "",
) -> AuditEvent:
    """Insert one event row. Raises on failure, the callers decide what happens then."""
    if action not in _VALID_ACTIONS:
        raise ValueError(f"unknown audit action {action!r}")
    # The savepoint keeps a failed insert from poisoning an outer
    # transaction the caller may be running in.
    with transaction.atomic():
        return AuditEvent.objects.create(
            actor=actor,
            action=action,
            resource_type=str(target_type)[:100],
            resource_id=str(target_id)[:64],
            correlation_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            extra=extra,
        )


def record_admin_event(
    *,
    operation: str,
    action: str,
    target_type: str,
    target_id: Any,
    request: Any = None,
    actor: Any = None,
    payload: Optional[dict] = None,
    summary: str = "",
) -> Optional[AuditEvent]:
    """
    Write one admin audit event and return it, or return None if it failed.

    Pass the DRF/Django ``request`` to pick up the actor and request id, or pass
    ``actor`` yourself. ``payload`` is run through ``redact()`` before it is
    stored, so callers do not need to clean it first.
    """
    try:
        extra = {
            "source": "admin_action",
            "operation": operation,
            "payload": redact(payload or {}),
        }
        if summary:
            extra["summary"] = redact_string(summary)
        return write_event(
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=_request_id(request),
            extra=extra,
            actor=_actor(request, actor),
        )
    except Exception:
        logger.exception(
            "Could not record admin audit event operation=%s target=%s#%s",
            operation,
            target_type,
            target_id,
        )
        return None
