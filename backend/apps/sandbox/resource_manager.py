import ast
import logging
import sys
import time

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.sandbox.models import ExecutionViolationLog

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    pass


class QuotaViolation(Exception):
    pass


class ResourceManagementEngine:
    MAX_EXECUTION_TIME_SECONDS = 5
    MAX_MEMORY_MB = 128
    MAX_CPU_TIME_SECONDS = 3
    MAX_CONCURRENT_EXECUTIONS = 2
    MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB
    MAX_SESSION_CPU_SECONDS = 30.0  # max 30s CPU time per session window
    MAX_SESSION_PROCESSES = 20  # max processes spawned across session
    SESSION_WINDOW_SECONDS = 3600  # 1 hour window

    # AST Whitelist rules
    FORBIDDEN_IMPORTS = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "pathlib",
        "shutil",
        "pty",
        "builtins",
        "importlib",
        "ctypes",
        "platform",
    }
    FORBIDDEN_FUNCTIONS = {
        "open",
        "eval",
        "exec",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "compile",
        "dir",
        "globals",
        "locals",
        "vars",
    }

    @classmethod
    def log_violation(
        cls, user_id: str, code: str, violation_type: str, details: str = ""
    ):
        user = None
        user_identifier = user_id
        User = get_user_model()
        if user_id.isdigit():
            try:
                user = User.objects.get(id=int(user_id))
            except User.DoesNotExist:
                pass

        ExecutionViolationLog.objects.create(
            user=user,
            user_identifier=user_identifier,
            code_snippet=code,
            violation_type=violation_type,
            details=details,
        )
        logger.warning(f"Violation [{violation_type}] by {user_identifier}: {details}")

    @classmethod
    def analyze_ast(cls, code: str):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityViolation(f"Syntax Error: {e}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in cls.FORBIDDEN_IMPORTS:
                        raise SecurityViolation(
                            f"Importing '{alias.name}' is forbidden for security reasons."
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in cls.FORBIDDEN_IMPORTS:
                    raise SecurityViolation(
                        f"Importing from '{node.module}' is forbidden."
                    )
            elif isinstance(node, ast.Name):
                if node.id in cls.FORBIDDEN_FUNCTIONS:
                    raise SecurityViolation(
                        f"Access to function '{node.id}' is disabled in the sandbox."
                    )
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__"):
                    raise SecurityViolation(
                        f"Access to magic attributes ('{node.attr}') is disabled."
                    )
            # Support ast.Constant (Python 3.8+) for double underscores
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "__" in node.value:
                    raise SecurityViolation(
                        "Double underscores in string literals are forbidden to prevent sandbox escape."
                    )

    @classmethod
    def check_session_quotas(cls, session_id: str) -> tuple[bool, str | None]:
        """Verify whether session is within concurrent, CPU, and process quotas."""
        # 1. Concurrent executions
        concurrency_key = f"sandbox_concurrent_executions_{session_id}"
        current_concurrent = cache.get(concurrency_key, 0)
        if current_concurrent >= cls.MAX_CONCURRENT_EXECUTIONS:
            return False, "concurrency"

        # 2. Cumulative CPU quota for this session window
        cpu_key = f"sandbox_session_cpu_{session_id}"
        current_cpu = float(cache.get(cpu_key, 0.0))
        if current_cpu >= cls.MAX_SESSION_CPU_SECONDS:
            return False, "cpu"

        # 3. Process count quota for this session window
        proc_key = f"sandbox_session_processes_{session_id}"
        current_procs = int(cache.get(proc_key, 0))
        if current_procs >= cls.MAX_SESSION_PROCESSES:
            return False, "process"

        return True, None

    @classmethod
    def check_and_acquire(cls, session_id: str) -> tuple[bool, str | None]:
        """Check all session quotas and acquire an execution slot if within limits."""
        allowed, reason = cls.check_session_quotas(session_id)
        if not allowed:
            return False, reason

        concurrency_key = f"sandbox_concurrent_executions_{session_id}"
        current = cache.get(concurrency_key, 0)
        cache.set(
            concurrency_key, current + 1, timeout=cls.MAX_EXECUTION_TIME_SECONDS * 2
        )

        proc_key = f"sandbox_session_processes_{session_id}"
        procs = int(cache.get(proc_key, 0))
        cache.set(proc_key, procs + 1, timeout=cls.SESSION_WINDOW_SECONDS)

        return True, None

    @classmethod
    def acquire_execution_lock(cls, session_id: str) -> bool:
        """Backwards compatible lock acquisition (returns True if acquired)."""
        allowed, _ = cls.check_and_acquire(session_id)
        return allowed

    @classmethod
    def record_session_usage(
        cls, session_id: str, cpu_time: float, output_bytes: int = 0
    ):
        """Record CPU usage and output bytes for the session."""
        cpu_key = f"sandbox_session_cpu_{session_id}"
        current_cpu = float(cache.get(cpu_key, 0.0))
        cache.set(
            cpu_key,
            current_cpu + max(0.0, cpu_time),
            timeout=cls.SESSION_WINDOW_SECONDS,
        )

    @classmethod
    def release_execution_lock(cls, session_id: str):
        """Release execution slot."""
        concurrency_key = f"sandbox_concurrent_executions_{session_id}"
        current = cache.get(concurrency_key, 0)
        if current > 0:
            cache.set(
                concurrency_key, current - 1, timeout=cls.MAX_EXECUTION_TIME_SECONDS * 2
            )

    @classmethod
    def get_session_quota_status(cls, session_id: str) -> dict:
        """Returns the current quota allocation and consumption for a session."""
        concurrency_key = f"sandbox_concurrent_executions_{session_id}"
        cpu_key = f"sandbox_session_cpu_{session_id}"
        proc_key = f"sandbox_session_processes_{session_id}"

        return {
            "session_id": session_id,
            "concurrent_executions": int(cache.get(concurrency_key, 0)),
            "max_concurrent_executions": cls.MAX_CONCURRENT_EXECUTIONS,
            "session_cpu_seconds_used": round(float(cache.get(cpu_key, 0.0)), 3),
            "max_session_cpu_seconds": cls.MAX_SESSION_CPU_SECONDS,
            "session_processes_used": int(cache.get(proc_key, 0)),
            "max_session_processes": cls.MAX_SESSION_PROCESSES,
            "max_memory_mb": cls.MAX_MEMORY_MB,
            "max_cpu_time_seconds": cls.MAX_CPU_TIME_SECONDS,
            "max_output_bytes": cls.MAX_OUTPUT_BYTES,
        }

    @classmethod
    def reset_session_quota(cls, session_id: str):
        """Reset all quota counters for the given session."""
        cache.delete(f"sandbox_concurrent_executions_{session_id}")
        cache.delete(f"sandbox_session_cpu_{session_id}")
        cache.delete(f"sandbox_session_processes_{session_id}")

    @classmethod
    def kill_process_tree(cls, pid: int):
        """Cross-platform termination of a process and any children spawned by it."""
        if not pid:
            return
        try:
            import os
            import signal
            import subprocess

            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
        except Exception as e:
            logger.warning("Error killing process tree %s: %s", pid, e)

    @classmethod
    def get_wrapper_script(cls, code: str) -> str:
        return f"""
import sys
try:
    import resource
    memory_limit = {cls.MAX_MEMORY_MB} * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    cpu_limit = {cls.MAX_CPU_TIME_SECONDS}
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    if hasattr(resource, 'RLIMIT_NPROC'):
        # Limit max child processes to 5 to protect process quota
        resource.setrlimit(resource.RLIMIT_NPROC, (5, 5))
except ImportError:
    pass

code = {repr(code)}

# NOTE: __builtins__ is the *builtins module* here (not a dict), because this
# script runs as the top-level `__main__` module (via `python -c`). Importing
# the module explicitly and using vars() works in both contexts.
import builtins
safe_builtins = {{k: v for k, v in vars(builtins).items() if k not in {cls.FORBIDDEN_FUNCTIONS}}}
safe_globals = {{"__builtins__": safe_builtins}}

try:
    exec(code, safe_globals)
except MemoryError:
    print("Error: Memory limit exceeded.", file=sys.stderr)
    sys.exit(137)
except Exception as e:
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"""


class SandboxResourceManager:
    """Atomic Redis-based distributed semaphore for sandbox execution."""

    MAX_CONCURRENT = 2
    LOCK_TTL = 60  # seconds
    CIRCUIT_BREAKER_THRESHOLD = 5

    def __init__(self):
        self.redis = redis.Redis.from_url(settings.REDIS_URL)
        self.semaphore_key = "sandbox:semaphore"
        self.counter_key = "sandbox:counter"
        self.failure_key = "sandbox:failures"

    def acquire_execution_lock(self) -> bool:
        """Acquire lock using atomic Redis INCR."""
        # Check circuit breaker
        failures = int(self.redis.get(self.failure_key) or 0)
        if failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            logger.warning("Circuit breaker open - blocking execution")
            return False

        # Atomic increment
        current = self.redis.incr(self.counter_key)

        # Set TTL on first creation
        if current == 1:
            self.redis.expire(self.counter_key, self.LOCK_TTL)

        if current <= self.MAX_CONCURRENT:
            logger.info(f"Lock acquired: {current}/{self.MAX_CONCURRENT}")
            return True

        # Exceeded limit - decrement and fail
        self.redis.decr(self.counter_key)
        logger.warning(f"Concurrency limit reached: {current}")
        return False

    def release_execution_lock(self):
        """Release lock using atomic Redis DECR."""
        current = self.redis.decr(self.counter_key)
        if current < 0:
            self.redis.set(self.counter_key, 0)

        # Reset failures on successful release
        self.redis.set(self.failure_key, 0)
        logger.info(f"Lock released: {current}/{self.MAX_CONCURRENT}")

    def record_failure(self):
        """Record failure for circuit breaker."""
        self.redis.incr(self.failure_key)
        self.redis.expire(self.failure_key, 300)  # 5 minutes

    def reset_circuit_breaker(self):
        """Reset circuit breaker."""
        self.redis.set(self.failure_key, 0)

    get_wrapper_script = ResourceManagementEngine.get_wrapper_script
