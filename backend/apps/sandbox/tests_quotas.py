import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

import django
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.sandbox.models import ExecutionViolationLog
from apps.sandbox.resource_manager import (
    ResourceManagementEngine,
    SecurityViolation,
)
from apps.sandbox.services import stream_python_execution


class SandboxSessionQuotaTestCase(unittest.TestCase):
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
