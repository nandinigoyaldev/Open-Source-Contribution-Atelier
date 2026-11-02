import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("audit")


class AuditLogger:
    """Structured JSON audit logging for compliance."""

    @staticmethod
    def log(
        user_id: Optional[str],
        action: str,
        resource: str,
        resource_id: Optional[str],
        method: str,
        ip_address: str,
        status_code: int,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        """Log audit event in JSON format."""

        audit_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id or "anonymous",
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "method": method,
            "ip_address": ip_address,
            "status_code": status_code,
            "request_id": str(uuid.uuid4()),
        }

        if request_data:
            # Sanitize sensitive data
            sanitized = AuditLogger._sanitize_data(request_data)
            audit_entry["request_data"] = sanitized

        if response_data:
            audit_entry["response_data"] = response_data

        if error:
            audit_entry["error"] = error

        # Log as JSON
        logger.info(json.dumps(audit_entry, default=str))

    SENSITIVE_KEY_PARTS = (
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
    )

    @staticmethod
    def _is_sensitive(key) -> bool:
        name = str(key).lower()
        return name == "key" or any(
            part in name for part in AuditLogger.SENSITIVE_KEY_PARTS
        )

    @staticmethod
    def _sanitize_data(data):
        """
        Remove sensitive fields from logs.

        Works on any JSON value: objects are sanitized key by key (``new_password``,
        ``access_token`` and similar count as sensitive, not just the exact names), lists
        are sanitized item by item, and other values are returned unchanged. A request
        body that is a list used to crash the logger and turn the request into a 500.
        """
        if isinstance(data, dict):
            return {
                key: (
                    "***REDACTED***"
                    if AuditLogger._is_sensitive(key)
                    else AuditLogger._sanitize_data(value)
                )
                for key, value in data.items()
            }
        if isinstance(data, (list, tuple)):
            return [AuditLogger._sanitize_data(item) for item in data]
        return data
