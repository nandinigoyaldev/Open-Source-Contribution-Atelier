import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

import django
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.sandbox.models import ExecutionViolationLog
from apps.sandbox.resource_manager import (
    QuotaViolation,
    ResourceManagementEngine,
    SecurityViolation,
)
from apps.sandbox.services import start_debug_session, stream_python_execution


class SandboxSessionQuotaTestCase(TestCase):
    def setUp(self):
        self.session_id = f"test_session_{os.urandom(4).hex()}"
        ResourceManagementEngine.reset_session_quota(self.session_id)
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username=f"quotauser_{os.urandom(4).hex()}",
            email="quotauser@example.com",
            password="password123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        ResourceManagementEngine.reset_session_quota(self.session_id)
        ResourceManagementEngine.reset_session_quota(str(self.user.id))

    def test_session_quota_status(self):
        """Verify initial quota status returns defaults and correct structures."""
        status_data = ResourceManagementEngine.get_session_quota_status(self.session_id)
        self.assertEqual(status_data["session_id"], self.session_id)
        self.assertEqual(status_data["concurrent_executions"], 0)
        self.assertEqual(
            status_data["max_concurrent_executions"],
            ResourceManagementEngine.MAX_CONCURRENT_EXECUTIONS,
        )
        self.assertEqual(status_data["session_cpu_seconds_used"], 0.0)
        self.assertEqual(
            status_data["max_session_cpu_seconds"],
            ResourceManagementEngine.MAX_SESSION_CPU_SECONDS,
        )
        self.assertEqual(status_data["session_processes_used"], 0)
        self.assertEqual(
            status_data["max_session_processes"],
            ResourceManagementEngine.MAX_SESSION_PROCESSES,
        )

    def test_concurrent_execution_quota(self):
        """Verify exceeding max concurrent executions blocks additional execution."""
        # Acquire up to limit
        for _ in range(ResourceManagementEngine.MAX_CONCURRENT_EXECUTIONS):
            allowed, reason = ResourceManagementEngine.check_and_acquire(
                self.session_id
            )
            self.assertTrue(allowed)
            self.assertIsNone(reason)

        # Exceed limit
        allowed, reason = ResourceManagementEngine.check_and_acquire(self.session_id)
        self.assertFalse(allowed)
        self.assertEqual(reason, "concurrency")

        # Release one and verify can acquire again
        ResourceManagementEngine.release_execution_lock(self.session_id)
        allowed, reason = ResourceManagementEngine.check_and_acquire(self.session_id)
        self.assertTrue(allowed)

    def test_cpu_quota_exhaustion(self):
        """Verify exceeding cumulative CPU quota blocks execution."""
        ResourceManagementEngine.record_session_usage(
            self.session_id,
            cpu_time=ResourceManagementEngine.MAX_SESSION_CPU_SECONDS + 1.0,
        )
        allowed, reason = ResourceManagementEngine.check_and_acquire(self.session_id)
        self.assertFalse(allowed)
        self.assertEqual(reason, "cpu")

    def test_process_quota_exhaustion(self):
        """Verify exceeding cumulative process quota blocks execution."""
        proc_key = f"sandbox_session_processes_{self.session_id}"
        cache.set(
            proc_key, ResourceManagementEngine.MAX_SESSION_PROCESSES, timeout=3600
        )

        allowed, reason = ResourceManagementEngine.check_and_acquire(self.session_id)
        self.assertFalse(allowed)
        self.assertEqual(reason, "process")

    def test_reset_session_quota(self):
        """Verify reset clears cumulative and concurrent session usage."""
        ResourceManagementEngine.record_session_usage(self.session_id, cpu_time=15.0)
        ResourceManagementEngine.check_and_acquire(self.session_id)

        ResourceManagementEngine.reset_session_quota(self.session_id)
        status_data = ResourceManagementEngine.get_session_quota_status(self.session_id)
        self.assertEqual(status_data["concurrent_executions"], 0)
        self.assertEqual(status_data["session_cpu_seconds_used"], 0.0)
        self.assertEqual(status_data["session_processes_used"], 0)

    def test_wrapper_script_contains_resource_limits(self):
        """Verify wrapper script generates RLIMIT and safe builtins."""
        script = ResourceManagementEngine.get_wrapper_script("print(123)")
        self.assertIn("RLIMIT_AS", script)
        self.assertIn("RLIMIT_CPU", script)
        self.assertIn("RLIMIT_NPROC", script)
        self.assertIn("safe_builtins", script)

    def test_session_quota_api_view(self):
        """Verify GET and DELETE /api/sandbox/quotas/ endpoints."""
        response = self.client.get("/api/sandbox/quotas/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["session_id"], str(self.user.id))
        self.assertIn("max_session_cpu_seconds", data)

        # Delete / reset quota
        del_response = self.client.delete("/api/sandbox/quotas/")
        self.assertEqual(del_response.status_code, status.HTTP_200_OK)

    def test_ast_forbidden_imports(self):
        """Verify AST rejects dangerous forbidden module imports."""
        with self.assertRaises(SecurityViolation):
            ResourceManagementEngine.analyze_ast("import os")
        with self.assertRaises(SecurityViolation):
            ResourceManagementEngine.analyze_ast("from subprocess import Popen")

    def test_git_verify_quota_exhaustion(self):
        """Verify SandboxVerifyView blocks requests when session quota is exhausted."""
        # Exhaust CPU quota for user
        ResourceManagementEngine.record_session_usage(
            str(self.user.id),
            cpu_time=ResourceManagementEngine.MAX_SESSION_CPU_SECONDS + 5.0,
        )
        response = self.client.post(
            "/api/sandbox/verify/",
            {"command": "git status", "expected_command": "git status"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        data = response.json()
        self.assertFalse(data["accepted"])
        self.assertEqual(data["quota_error"], "cpu")
        self.assertIn("metrics", data)
        self.assertEqual(data["metrics"]["session_id"], str(self.user.id))

    def test_debugger_session_quota_exhaustion(self):
        """Verify debugger flow enforces session quotas."""
        # Exhaust process quota
        proc_key = f"sandbox_session_processes_{self.session_id}"
        cache.set(
            proc_key, ResourceManagementEngine.MAX_SESSION_PROCESSES, timeout=3600
        )

        loop = asyncio.new_event_loop()
        try:
            with self.assertRaises(QuotaViolation) as cm:
                loop.run_until_complete(
                    start_debug_session("x = 1", [], user_id=self.session_id)
                )
            self.assertEqual(cm.exception.violation_type, "process")
        finally:
            loop.close()

    def test_concurrent_sessions_isolation(self):
        """Verify session quotas are strictly isolated across multiple sessions."""
        session_a = f"session_a_{os.urandom(4).hex()}"
        session_b = f"session_b_{os.urandom(4).hex()}"

        try:
            # Exhaust session A
            ResourceManagementEngine.record_session_usage(
                session_a, cpu_time=ResourceManagementEngine.MAX_SESSION_CPU_SECONDS
            )
            allowed_a, reason_a = ResourceManagementEngine.check_session_quotas(
                session_a
            )
            self.assertFalse(allowed_a)
            self.assertEqual(reason_a, "cpu")

            # Session B should remain uninhibited
            allowed_b, reason_b = ResourceManagementEngine.check_session_quotas(
                session_b
            )
            self.assertTrue(allowed_b)
            self.assertIsNone(reason_b)
        finally:
            ResourceManagementEngine.reset_session_quota(session_a)
            ResourceManagementEngine.reset_session_quota(session_b)

    def test_cgroup_v2_resource_limit_constants(self):
        """Verify cgroup v2 specifications match CPU 50%, 256MB RAM, and 32 PIDs."""
        self.assertEqual(ResourceManagementEngine.CGROUP_CPU_MAX, "50000 100000")
        self.assertEqual(ResourceManagementEngine.CGROUP_MEMORY_MAX, "268435456")
        self.assertEqual(ResourceManagementEngine.CGROUP_PIDS_MAX, 32)
        self.assertEqual(ResourceManagementEngine.MAX_MEMORY_MB, 256)
        self.assertEqual(
            ResourceManagementEngine.QUOTA_EXCEEDED_MESSAGE,
            "Resource quota exceeded: Memory or process limit reached",
        )

    def test_cgroup_v2_budget_manager_mock_setup(self):
        """Verify cgroup v2 creates group, sets cpu.max, memory.max, pids.max and attaches PID."""
        import tempfile
        from pathlib import Path

        from apps.sandbox.resource_manager import CgroupV2BudgetManager

        with tempfile.TemporaryDirectory() as td:
            cg_root = Path(td)
            # Create mock cgroup.controllers indicating cgroup v2 presence
            (cg_root / "cgroup.controllers").write_text(
                "cpu memory pids\n", encoding="utf-8"
            )

            manager = CgroupV2BudgetManager(cgroup_root=str(cg_root))
            self.assertTrue(manager.is_cgroup_v2_available())

            proc_cgroup = manager.setup_process_cgroup(
                pid=9999, scope_name="test_worker_9999"
            )
            self.assertIsNotNone(proc_cgroup)

            cg_path = Path(proc_cgroup)
            self.assertTrue(cg_path.exists())
            self.assertEqual(
                (cg_path / "cpu.max").read_text(encoding="utf-8").strip(),
                "50000 100000",
            )
            self.assertEqual(
                (cg_path / "memory.max").read_text(encoding="utf-8").strip(),
                "268435456",
            )
            self.assertEqual(
                (cg_path / "pids.max").read_text(encoding="utf-8").strip(), "32"
            )
            self.assertEqual(
                (cg_path / "cgroup.procs").read_text(encoding="utf-8").strip(), "9999"
            )

            # Test violation detection
            (cg_path / "memory.events").write_text(
                "oom_kill 1\noom 1\n", encoding="utf-8"
            )
            breached, reason = manager.check_limits_breached(proc_cgroup)
            self.assertTrue(breached)
            self.assertEqual(reason, "memory")

            (cg_path / "memory.events").write_text("oom_kill 0\n", encoding="utf-8")
            (cg_path / "pids.events").write_text("max 3\n", encoding="utf-8")
            breached, reason = manager.check_limits_breached(proc_cgroup)
            self.assertTrue(breached)
            self.assertEqual(reason, "process")

            # Test cleanup
            manager.terminate_cgroup(proc_cgroup)

    def test_terminate_process_cleanly_message(self):
        """Verify clean process termination returns the exact user-facing quota exceeded message."""
        msg = ResourceManagementEngine.terminate_process_cleanly(pid=0)
        self.assertEqual(
            msg,
            "Resource quota exceeded: Memory or process limit reached",
        )

    def test_wrapper_script_cgroup_quota_exceeded_message(self):
        """Verify wrapper script enforces 256MB RAM and outputs the quota exceeded message on limit breaches."""
        script = ResourceManagementEngine.get_wrapper_script("print('test')")
        self.assertIn("268435456", script)
        self.assertIn("RLIMIT_NPROC, (32, 32)", script)
        self.assertIn(
            "Resource quota exceeded: Memory or process limit reached", script
        )
