import logging
import re
import traceback


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter to obscure sensitive PII data (emails and tokens) from logs.
    """

    # 1. Email pattern
    EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

    # 2. JWT pattern (eyJ... followed by base64-like characters, dot, etc.)
    JWT_PATTERN = re.compile(
        r"\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+\b"
    )

    # 3. Authorization header / token patterns in text/logs
    # Matches patterns like: Authorization: Bearer <token>, Token: <token>, token = <token>, access_token = <token>
    TOKEN_KEYVALUE_PATTERN = re.compile(
        r'(?i)\b(authorization|bearer|token|password|secret|access_token|refresh_token|otp_token)\b(\s*[:=]\s*|\s+)(["\']?)(?P<value>[a-zA-Z0-9-_+/=]{8,})\3'
    )

    def mask_text(self, text: str) -> str:
        if not isinstance(text, str):
            return text

        # Mask JWT tokens
        text = self.JWT_PATTERN.sub("[MASKED_TOKEN]", text)

        # Mask emails
        text = self.EMAIL_PATTERN.sub("[MASKED_EMAIL]", text)

        # Mask token/secret key-value pairs
        def replace_kv(match):
            key = match.group(1)
            separator = match.group(2)
            quote = match.group(3)
            return f"{key}{separator}{quote}[MASKED]{quote}"

        text = self.TOKEN_KEYVALUE_PATTERN.sub(replace_kv, text)

        return text

    def filter(self, record: logging.LogRecord) -> bool:
        # Pre-format message if args exist to prevent formatting issues after masking
        if record.args:
            try:
                record.msg = record.msg % record.args
                record.args = ()
            except Exception:
                pass

        if isinstance(record.msg, str):
            record.msg = self.mask_text(record.msg)

        # If traceback exists, pre-format and mask it so it won't be formatted with unmasked data later
        if record.exc_info:
            try:
                exc_list = traceback.format_exception(*record.exc_info)
                exc_text = "".join(exc_list)
                record.exc_text = self.mask_text(exc_text)
            except Exception:
                pass
        elif getattr(record, "exc_text", None) and isinstance(record.exc_text, str):
            record.exc_text = self.mask_text(record.exc_text)

        return True
