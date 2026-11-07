"""
Audit events for signed-out security flows, such as password reset.

These use the same ``AuditEvent`` table and the same redaction as
``admin_events``, with two differences. ``extra["source"]`` is ``"security"``,
and the client's address and user agent are kept, because with nobody signed in
they are the only way to connect repeated attempts.

Recording an event must never break the flow it describes, so
``record_security_event`` catches everything and logs it.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any, Optional

from apps.audit.admin_events import write_event
from apps.audit.models import AuditEvent
from apps.audit.redaction import redact

logger = logging.getLogger(__name__)

SOURCE = "security"

_MAX_REQUEST_ID_LENGTH = 64
_MAX_USER_AGENT_LENGTH = 512


def _valid_ip(value: Any) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        return None


def record_security_event(
    *,
    operation: str,
    target_type: str,
    target_id: Any,
    action: str = AuditEvent.ACTION_CREATED,
    payload: Optional[dict] = None,
    ip_address: Any = None,
    user_agent: str = "",
    request_id: str = "",
) -> Optional[AuditEvent]:
    """
    Write one security event and return it, or return None if it failed.

    ``payload`` is run through ``redact()`` before it is stored. Pass plain
    client values rather than a request, so this also works from a queued task.
    """
    try:
        return write_event(
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=str(request_id or "")[:_MAX_REQUEST_ID_LENGTH],
            extra={
                "source": SOURCE,
                "operation": operation,
                "payload": redact(payload or {}),
            },
            ip_address=_valid_ip(ip_address),
            user_agent=str(user_agent or "")[:_MAX_USER_AGENT_LENGTH],
        )
    except Exception:
        logger.exception(
            "Could not record security audit event operation=%s target=%s#%s",
            operation,
            target_type,
            target_id,
        )
        return None
