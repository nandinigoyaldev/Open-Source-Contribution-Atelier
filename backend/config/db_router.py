import logging
import random
import sys
import time

from django.conf import settings
from django.db import connections, transaction
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


class PrimaryReplicaRouter:
    """
    A database router to route read operations to read replicas,
    and write operations to the primary database.
    Supports load balancing, graceful fallback, and transactional consistency.
    """

    def __init__(self):
        # Identify all configured read replicas based on 'replica' prefix
        self.replicas = [db for db in settings.DATABASES if db.startswith("replica")]
        self._dead_replicas = {}
        self._dead_timeout = 60  # Retry a down replica after 60 seconds

    def _get_healthy_replica(self):
        if not self.replicas:
            return "default"

        now = time.time()
        available = []
        for r in self.replicas:
            if r in self._dead_replicas:
                if now - self._dead_replicas[r] > self._dead_timeout:
                    del self._dead_replicas[r]
                    available.append(r)
            else:
                available.append(r)

        if not available:
            logger.warning(
                "All read replicas are unavailable. Falling back to primary database."
            )
            return "default"

        random.shuffle(available)

        for replica in available:
            connection = connections[replica]
            if connection.connection is not None:
                return replica
            else:
                try:
                    connection.ensure_connection()
                    return replica
                except OperationalError as e:
                    logger.warning(
                        f"Replica {replica} is unhealthy or unavailable: {e}"
                    )
                    self._dead_replicas[replica] = time.time()
                    continue

        return "default"

    def db_for_read(self, model, **hints):
        """
        Reads go to a healthy replica database unless running tests or in a transaction.
        """
        if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
            return "default"

        # Ensure transactional consistency: if we're in an atomic write block on the primary,
        # route reads to the primary to prevent stale reads immediately after writes.
        if transaction.get_connection("default").in_atomic_block:
            return "default"

        return self._get_healthy_replica()

    def db_for_write(self, model, **hints):
        """
        Writes always go to primary.
        """
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the primary or any replica is involved.
        """
        db_set = {"default"} | set(self.replicas)
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        All non-auth models end up in this pool.
        Ensure that we only migrate the primary database.
        """
        if db in self.replicas or db.startswith("replica"):
            return False
        return True
