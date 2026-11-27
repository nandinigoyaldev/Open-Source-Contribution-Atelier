"""
Worker start hooks that report task locks left behind by a dead worker.
"""

import logging

from celery.signals import worker_ready
from django_q.signals import post_spawn

from apps.core.locks import find_stranded_locks

logger = logging.getLogger(__name__)


def report_stranded_locks(**kwargs):
    try:
        for lock in find_stranded_locks():
            logger.warning(
                f"Stranded task lock {lock['key']} (host {lock['host']}, "
                f"pid {lock['pid']}): {lock['reason']}, "
                f"expires in {lock['ttl']:.0f}s"
            )
    except Exception as e:
        # A worker must still start when Redis is unreachable.
        logger.warning(f"Could not check for stranded task locks: {e}")


worker_ready.connect(report_stranded_locks)
# Django-Q: also fires when a worker that was killed gets replaced.
post_spawn.connect(report_stranded_locks)
