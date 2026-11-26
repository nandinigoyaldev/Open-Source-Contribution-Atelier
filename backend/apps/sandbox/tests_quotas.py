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

    def test_container_capabilities_drop_all_except_setuid_setgid(self):
        """Verify Docker sandbox container security profile drops all capabilities except CAP_SETUID and CAP_SETGID."""
        config = ResourceManagementEngine.get_container_security_config()
        self.assertEqual(config.get("cap_drop"), ["ALL"])
        self.assertEqual(sorted(config.get("cap_add", [])), ["SETGID", "SETUID"])
        self.assertTrue(config.get("ebpf_filter_enabled"))
        self.assertTrue(config.get("block_outbound_network"))

    def test_network_isolation_blocks_external_destinations(self):
        """Verify outbound network connections to non-loopback IPs and domains are rejected."""
        with self.assertRaises(SecurityViolation):
            ResourceManagementEngine.validate_network_access("8.8.8.8")
        with self.assertRaises(SecurityViolation):
            ResourceManagementEngine.validate_network_access("example.com")
        with self.assertRaises(SecurityViolation):
            ResourceManagementEngine.validate_network_access("192.168.1.100")
        with self.assertRaises(SecurityViolation):
            ResourceManagementEngine.validate_network_access("10.0.0.1")

    def test_network_isolation_permits_whitelisted_loopback(self):
        """Verify only whitelisted loopback addresses (127.0.0.1, localhost, ::1) are allowed."""
        self.assertTrue(ResourceManagementEngine.validate_network_access("127.0.0.1"))
        self.assertTrue(ResourceManagementEngine.validate_network_access("localhost"))
        self.assertTrue(ResourceManagementEngine.validate_network_access("::1"))
        self.assertTrue(ResourceManagementEngine.validate_network_access("127.0.0.5"))

    def test_sandbox_seccomp_profile_structure(self):
        """Verify infra/docker/sandbox-seccomp.json is valid and enforces restricted syscalls."""
        import json
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        seccomp_path = repo_root / "infra" / "docker" / "sandbox-seccomp.json"
        self.assertTrue(seccomp_path.exists())

        with open(seccomp_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        self.assertEqual(profile.get("defaultAction"), "SCMP_ACT_ERRNO")
        self.assertIn("architectures", profile)
        self.assertIn("syscalls", profile)

        # Check blocked syscalls category
        actions = {s.get("action") for s in profile["syscalls"]}
        self.assertIn("SCMP_ACT_ALLOW", actions)
        self.assertIn("SCMP_ACT_ERRNO", actions)

    def test_sandbox_apparmor_and_ebpf_profile_files_exist(self):
        """Verify AppArmor profile and eBPF network filter C source exist in infra/docker/."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        apparmor_path = repo_root / "infra" / "docker" / "sandbox-apparmor.profile"
        ebpf_path = repo_root / "infra" / "docker" / "ebpf_network_filter.c"

        self.assertTrue(apparmor_path.exists())
        self.assertTrue(ebpf_path.exists())

        with open(apparmor_path, "r", encoding="utf-8") as f:
            apparmor_content = f.read()
        self.assertIn("profile sandbox-profile", apparmor_content)
        self.assertIn("capability setuid", apparmor_content)
        self.assertIn("capability setgid", apparmor_content)
        self.assertIn("deny capability sys_admin", apparmor_content)

        with open(ebpf_path, "r", encoding="utf-8") as f:
            ebpf_content = f.read()
        self.assertIn("filter_outbound_ipv4", ebpf_content)
        self.assertIn("filter_outbound_ipv6", ebpf_content)
        self.assertIn("LOOPBACK_IPV4_MASK", ebpf_content)

    def test_wrapper_script_network_isolation_socket_hook(self):
        """Verify generated wrapper script patches socket.connect to block non-loopback connections."""
        script = ResourceManagementEngine.get_wrapper_script("print('secure')")
        self.assertIn("_isolated_connect", script)
        self.assertIn("Network access to", script)
        self.assertIn("127.0.0.1", script)
        self.assertIn("localhost", script)
        self.assertIn("socket.socket.connect = _isolated_connect", script)
