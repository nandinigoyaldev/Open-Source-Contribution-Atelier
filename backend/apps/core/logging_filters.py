import logging
from apps.core.middleware.request_id import get_request_id, get_user_id


class RequestIdFilter(logging.Filter):
    """
    Logging filter that injects the current request_id and user_id into log records.
    """

    def filter(self, record):
        record.request_id = get_request_id() or "-"
        record.user_id = get_user_id() or "-"
        return True
