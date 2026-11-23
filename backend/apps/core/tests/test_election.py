"""
Unit tests for distributed leader election and worker coordination.
===================================================================
Verifies:
- Redis key leasing (SET leader_id NX EX 15) for leader election.
- Multi-worker coordination: only one node acquires leadership.
- Lease renewal via atomic Lua script.
- Seamless failover: follower claims leadership when leader lease expires.
- Voluntary step-down.
- Prometheus monitoring gauge notification_worker_is_leader (1=leader, 0=follower).
- @leader_only decorator and scheduled task protection.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.election import (
    _RENEW_LUA_SCRIPT,
    _STEP_DOWN_LUA_SCRIPT,
    LeaderElectionService,
    get_default_election_service,
    is_worker_leader,
    leader_guard,
    leader_only,
    set_default_election_service,
)
from apps.notifications.metrics import (
    LEADER_GAUGE_NAME,
    get_worker_is_leader_metric,
    set_worker_is_leader_metric,
)
from apps.notifications.tasks import (
    dispatch_notification_outbox,
    purge_notification_ledger_task,
    send_notification_digests,
)


class MockRedisServer:
    """Simulates Redis key-value store with TTL and atomic Lua evaluation."""

    def __init__(self):
        self.store = {}
        self.ttl_store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value.encode("utf-8") if isinstance(value, str) else value
        if ex:
            self.ttl_store[key] = ex
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        deleted = key in self.store
        self.store.pop(key, None)
        self.ttl_store.pop(key, None)
        return 1 if deleted else 0

    def expire(self, key, seconds):
        if key in self.store:
            self.ttl_store[key] = seconds
            return 1
        return 0

    def eval(self, script, numkeys, *args):
        # Support renewal and step down scripts
        key = args[0]
        node_id = args[1]
        current_val = self.store.get(key)
        expected_val = node_id.encode("utf-8") if isinstance(node_id, str) else node_id

        if script == _RENEW_LUA_SCRIPT:
            ttl = int(args[2])
            if current_val == expected_val:
                self.ttl_store[key] = ttl
                return 1
            return 0
        elif script == _STEP_DOWN_LUA_SCRIPT:
            if current_val == expected_val:
                self.store.pop(key, None)
                self.ttl_store.pop(key, None)
                return 1
            return 0
        return 0


class LeaderElectionTests(TestCase):
    def setUp(self):
        self.redis_server = MockRedisServer()
        self.key = "test:leader:notification_worker"
        self.node1 = LeaderElectionService(
            key=self.key,
            node_id="worker-node-1",
            ttl=15,
            redis_client=self.redis_server,
        )
        self.node2 = LeaderElectionService(
            key=self.key,
            node_id="worker-node-2",
            ttl=15,
            redis_client=self.redis_server,
        )
        set_default_election_service(None)

    def tearDown(self):
        set_default_election_service(None)
        self.node1.step_down()
        self.node2.step_down()

    def test_acquire_leadership_via_set_nx_ex(self):
        """
        Node 1 successfully claims leadership on an unheld key using SET NX EX 15.
        Gauge is updated to 1.
        """
        acquired = self.node1.acquire_leadership()

        self.assertTrue(acquired)
        self.assertTrue(self.node1.is_leader())
        self.assertEqual(self.node1.get_current_leader(), "worker-node-1")
        self.assertEqual(self.redis_server.ttl_store.get(self.key), 15)
        self.assertEqual(get_worker_is_leader_metric(), 1.0)

    def test_follower_cannot_claim_active_leadership(self):
        """
        When Node 1 holds the lease, Node 2's acquire attempt fails (NX constraint).
        Node 2 remains a follower with gauge 0.
        """
        self.node1.acquire_leadership()

        node2_acquired = self.node2.acquire_leadership()

        self.assertFalse(node2_acquired)
        self.assertFalse(self.node2.is_leader())
        self.assertEqual(self.node2.get_current_leader(), "worker-node-1")
        # Metric reflects current node2 state (0)
        self.assertEqual(get_worker_is_leader_metric(), 0.0)

    def test_leader_renews_lease_atomically(self):
        """
        Leader node successfully extends its lease within the 15-second window.
        """
        self.node1.acquire_leadership()

        # Update TTL in store to simulate time passage
        self.redis_server.ttl_store[self.key] = 8

        renewed = self.node1.renew_leadership()
        self.assertTrue(renewed)
        self.assertTrue(self.node1.is_leader())
        # TTL reset back to 15
        self.assertEqual(self.redis_server.ttl_store[self.key], 15)
        self.assertEqual(get_worker_is_leader_metric(), 1.0)

    def test_follower_cannot_renew_other_nodes_lease(self):
        """
        Follower node attempting to renew another node's lease is rejected by the Lua script.
        """
        self.node1.acquire_leadership()

        # Node 2 tries to renew
        renewed = self.node2.renew_leadership()
        self.assertFalse(renewed)
        self.assertFalse(self.node2.is_leader())

    def test_follower_seamlessly_claims_leadership_when_leader_lease_expires(self):
        """
        If Node 1 fails to renew its lease (e.g. crash or 15s timeout),
        the key expires and Node 2 seamlessly claims leadership on its next election cycle.
        """
        self.node1.acquire_leadership()
        self.assertEqual(self.node1.get_current_leader(), "worker-node-1")

        # Simulate 15s expiration of Node 1's key
        self.redis_server.store.pop(self.key, None)
        self.redis_server.ttl_store.pop(self.key, None)

        # Node 2 runs its election cycle
        claimed = self.node2.run_election_cycle()

        self.assertTrue(claimed)
        self.assertTrue(self.node2.is_leader())
        self.assertEqual(self.node2.get_current_leader(), "worker-node-2")
        self.assertEqual(get_worker_is_leader_metric(), 1.0)

    def test_voluntary_step_down(self):
        """
        When the leader steps down, the key is deleted and leadership is relinquished.
        Another node can claim leadership immediately.
        """
        self.node1.acquire_leadership()
        self.assertTrue(self.node1.is_leader())

        stepped_down = self.node1.step_down()
        self.assertTrue(stepped_down)
        self.assertFalse(self.node1.is_leader())
        self.assertIsNone(self.node1.get_current_leader())
        self.assertEqual(get_worker_is_leader_metric(), 0.0)

        # Now Node 2 can claim
        self.assertTrue(self.node2.acquire_leadership())
        self.assertEqual(self.node2.get_current_leader(), "worker-node-2")

    def test_leader_only_decorator(self):
        """
        Tasks wrapped with @leader_only execute when caller is leader,
        and return a skipped status dictionary when caller is follower.
        """
        set_default_election_service(self.node1)

        @leader_only
        def perform_fan_out():
            return {"status": "broadcasted", "items": 10}

        # Case 1: Node 1 is not yet leader -> task skips
        res_skipped = perform_fan_out()
        self.assertEqual(res_skipped.get("status"), "skipped")
        self.assertEqual(res_skipped.get("reason"), "not_leader")

        # Case 2: Node 1 acquires leadership -> task executes
        self.node1.acquire_leadership()
        res_executed = perform_fan_out()
        self.assertEqual(res_executed.get("status"), "broadcasted")
        self.assertEqual(res_executed.get("items"), 10)

    def test_leader_guard_context_manager(self):
        """
        with leader_guard() yields True for leader, False for follower.
        """
        with leader_guard(self.node1) as is_leader:
            self.assertFalse(is_leader)

        self.node1.acquire_leadership()
        with leader_guard(self.node1) as is_leader:
            self.assertTrue(is_leader)

    @override_settings(ENABLE_LEADER_ELECTION=True)
    def test_notification_scheduled_tasks_guard_followers(self):
        """
        Scheduled fan-out broadcasting and ledger generation tasks skip execution
        when run by a follower node.
        """
        set_default_election_service(self.node1)

        # Node 1 is not leader
        res_digests = send_notification_digests()
        self.assertEqual(res_digests, {"status": "skipped", "reason": "not_leader"})

        res_outbox = dispatch_notification_outbox()
        self.assertEqual(res_outbox, {"status": "skipped", "reason": "not_leader"})

        res_ledger = purge_notification_ledger_task()
        self.assertEqual(res_ledger, {"status": "skipped", "reason": "not_leader"})
