import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger('audit')

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
        logger.info(json.dumps(audit_entry))

    @staticmethod
    def _sanitize_data(data: Dict) -> Dict:
        """Remove sensitive fields from logs."""
        sensitive_fields = ['password', 'token', 'secret', 'key', 'authorization']
        sanitized = {}
        
        for key, value in data.items():
            if key.lower() in sensitive_fields:
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                sanitized[key] = AuditLogger._sanitize_data(value)
            else:
                sanitized[key] = value
                
        return sanitized