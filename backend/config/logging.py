"""
Advanced logging configuration with structured JSON logging and correlation ID support.
"""

import logging
import json
import time
import uuid
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger
from datetime import datetime
import re

# Sensitive data patterns to redact
SENSITIVE_PATTERNS = [
    (r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', 'password": "***REDACTED***"'),
    (r'token["\']?\s*[:=]\s*["\'][^"\']+["\']', 'token": "***REDACTED***"'),
    (r'authorization["\']?\s*[:=]\s*["\'][^"\']+["\']', 'authorization": "***REDACTED***"'),
    (r'api_key["\']?\s*[:=]\s*["\'][^"\']+["\']', 'api_key": "***REDACTED***"'),
    (r'secret["\']?\s*[:=]\s*["\'][^"\']+["\']', 'secret": "***REDACTED***"'),
]

class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive information from logs."""
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg, flags=re.IGNORECASE)
        return True

class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation_id to all log records."""
    
    def filter(self, record):
        from config.middleware import get_current_correlation_id
        record.correlation_id = get_current_correlation_id() or 'no-correlation-id'
        return True

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Add correlation ID
        from config.middleware import get_current_correlation_id
        log_record['correlation_id'] = get_current_correlation_id() or 'no-correlation-id'
        
        # Add user context if available
        from config.middleware import get_current_user
        user = get_current_user()
        if user:
            log_record['user_id'] = user.id
            log_record['username'] = user.username
        
        # Add request context
        from config.middleware import get_current_request
        request = get_current_request()
        if request:
            log_record['path'] = request.path
            log_record['method'] = request.method
            log_record['ip'] = request.META.get('REMOTE_ADDR')
            log_record['user_agent'] = request.META.get('HTTP_USER_AGENT')
        
        # Remove sensitive fields
        if 'password' in log_record:
            del log_record['password']
        if 'token' in log_record:
            del log_record['token']

def setup_logging():
    """Configure structured logging for the entire application."""
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler (for development)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(correlation_id)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(CorrelationIdFilter())
    logger.addHandler(console_handler)
    
    # File handler (JSON format)
    file_handler = logging.FileHandler('logs/app.log')
    file_handler.setLevel(logging.INFO)
    json_formatter = CustomJsonFormatter(
        'timestamp level logger module function line correlation_id message'
    )
    file_handler.setFormatter(json_formatter)
    file_handler.addFilter(CorrelationIdFilter())
    file_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.FileHandler('logs/error.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    error_handler.addFilter(CorrelationIdFilter())
    error_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(error_handler)
    
    return logger

# Initialize logging
setup_logging()