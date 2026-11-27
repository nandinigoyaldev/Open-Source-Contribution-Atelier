import ast
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.sandbox.models import ExecutionViolationLog

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    pass


class QuotaViolation(Exception):
    def __init__(self, message: str, violation_type: str = "quota"):
        super().__init__(message)
        self.violation_type = violation_type


class CgroupV2BudgetManager:
    """
    Linux cgroup v2 resource budgeting manager for sandbox execution workers.
    Enforces per-execution limits:
      - cpu.max = "50000 100000" (max 50% single CPU core)
      - memory.max = "268435456" (max 256MB RAM in bytes)
      - pids.max = 32 (max 32 concurrent processes/threads)
    """

    DEFAULT_CGROUP_ROOT = "/sys/fs/cgroup"
    DEFAULT_SLICE_NAME = "sandbox_workers"
    CPU_MAX = "50000 100000"
    MEMORY_MAX = "268435456"
    PIDS_MAX = 32
    QUOTA_EXCEEDED_MESSAGE = "Resource quota exceeded: Memory or process limit reached"

    def __init__(self, cgroup_root: Optional[str] = None):
        self.cgroup_root = Path(
            cgroup_root or os.environ.get("CGROUP_V2_PATH", self.DEFAULT_CGROUP_ROOT)
        )
        self.slice_dir = self.cgroup_root / self.DEFAULT_SLICE_NAME

    def is_cgroup_v2_available(self) -> bool:
        """Checks if Linux cgroup v2 filesystem is mounted and accessible."""
        try:
            return (
                self.cgroup_root.is_dir()
                and (self.cgroup_root / "cgroup.controllers").is_file()
            )
        except (PermissionError, OSError):
            return False

    def setup_process_cgroup(
        self, pid: int, scope_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Creates a dedicated cgroup v2 for the sandbox process and applies limits:
          - cpu.max: "50000 100000"
          - memory.max: "268435456"
          - pids.max: 32
        Attaches the given process PID to the cgroup.
        Returns the path of the created cgroup or None if cgroups v2 is unavailable.
        """
        if not pid or not self.is_cgroup_v2_available():
            return None

        scope = scope_name or f"worker_{pid}_{int(time.time())}"
        proc_cgroup = self.slice_dir / scope

        try:
            # Ensure slice directory exists and has subtree controllers enabled
            self.slice_dir.mkdir(parents=True, exist_ok=True)
            subtree_control = self.slice_dir / "cgroup.subtree_control"
            if subtree_control.exists():
                try:
                    with open(subtree_control, "w", encoding="utf-8") as f:
                        f.write("+cpu +memory +pids\n")
                except OSError:
                    pass

            proc_cgroup.mkdir(parents=True, exist_ok=True)

            # Apply CPU limit (50% single CPU core: 50,000us per 100,000us)
            cpu_file = proc_cgroup / "cpu.max"
            with open(cpu_file, "w", encoding="utf-8") as f:
                f.write(f"{self.CPU_MAX}\n")

            # Apply Memory limit (256MB = 268435456 bytes)
            mem_file = proc_cgroup / "memory.max"
            with open(mem_file, "w", encoding="utf-8") as f:
                f.write(f"{self.MEMORY_MAX}\n")

            # Apply PIDs limit (max 32 processes)
            pids_file = proc_cgroup / "pids.max"
            with open(pids_file, "w", encoding="utf-8") as f:
                f.write(f"{self.PIDS_MAX}\n")

            # Attach PID to cgroup
            procs_file = proc_cgroup / "cgroup.procs"
            with open(procs_file, "w", encoding="utf-8") as f:
                f.write(f"{pid}\n")

            logger.info(
                "Attached PID %s to cgroup v2 %s (cpu.max=%s, memory.max=%s, pids.max=%s)",
                pid,
                proc_cgroup,
                self.CPU_MAX,
                self.MEMORY_MAX,
                self.PIDS_MAX,
            )
            return str(proc_cgroup)
        except (PermissionError, OSError) as e:
            logger.warning(
                "Could not set up cgroup v2 for PID %s at %s: %s", pid, proc_cgroup, e
            )
            return None

    def check_limits_breached(self, cgroup_path: Optional[str]) -> tuple[bool, str]:
        """
        Inspects cgroup events to check if memory (OOM) or PIDs limits were breached.
        Returns (is_breached, reason).
        """
        if not cgroup_path:
            return False, ""

        cg_dir = Path(cgroup_path)
        if not cg_dir.exists():
            return False, ""

        # Check memory.events (oom_kill or oom)
        mem_events_file = cg_dir / "memory.events"
        if mem_events_file.exists():
            try:
                content = mem_events_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    parts = line.strip().split()
                    if len(parts) == 2:
                        key, val = parts[0], parts[1]
                        if key in ("oom_kill", "oom") and int(val) > 0:
                            return True, "memory"
            except (OSError, ValueError):
                pass

        # Check pids.events (max)
        pids_events_file = cg_dir / "pids.events"
        if pids_events_file.exists():
            try:
                content = pids_events_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    parts = line.strip().split()
                    if len(parts) == 2:
                        key, val = parts[0], parts[1]
                        if key == "max" and int(val) > 0:
                            return True, "process"
            except (OSError, ValueError):
                pass

        return False, ""

    def terminate_cgroup(self, cgroup_path: Optional[str]) -> None:
        """
        Cleanly terminates all processes in the cgroup and removes the directory.
        """
        if not cgroup_path:
            return

        cg_dir = Path(cgroup_path)
        if not cg_dir.exists():
            return

        try:
            # Modern cgroup v2 kill controller (Linux 5.14+)
            kill_file = cg_dir / "cgroup.kill"
            if kill_file.exists():
                try:
                    with open(kill_file, "w", encoding="utf-8") as f:
                        f.write("1\n")
                except OSError:
                    pass

            # Fallback: kill remaining PIDs in cgroup.procs
            procs_file = cg_dir / "cgroup.procs"
            if procs_file.exists():
                try:
                    pids = procs_file.read_text(encoding="utf-8").split()
                    for p in pids:
                        try:
                            import signal

                            os.kill(int(p), signal.SIGKILL)
                        except (OSError, ValueError):
                            pass
                except OSError:
                    pass

            # Remove cgroup directory
            try:
                cg_dir.rmdir()
            except OSError:
                pass
        except Exception as e:
            logger.warning("Error cleaning up cgroup %s: %s", cgroup_path, e)


class ResourceManagementEngine:
    MAX_EXECUTION_TIME_SECONDS = 5
    MAX_MEMORY_MB = 256
    MAX_CPU_TIME_SECONDS = 3
    MAX_CONCURRENT_EXECUTIONS = 2
    MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB
    MAX_SESSION_CPU_SECONDS = 30.0  # max 30s CPU time per session window
    MAX_SESSION_PROCESSES = 20  # max processes spawned across session
    SESSION_WINDOW_SECONDS = 3600  # 1 hour window

    # Cgroup v2 resource limits
    CGROUP_CPU_MAX = "50000 100000"  # max 50% single CPU core
    CGROUP_MEMORY_MAX = "268435456"  # max 256MB RAM in bytes
    CGROUP_PIDS_MAX = 32  # max 32 concurrent pids
    RESOURCE_QUOTA_EXCEEDED_MESSAGE = (
        "Resource quota exceeded: Memory or process limit reached"
    )
    QUOTA_EXCEEDED_MESSAGE = RESOURCE_QUOTA_EXCEEDED_MESSAGE

    cgroup_manager = CgroupV2BudgetManager()

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
    def apply_cgroup_v2_limits(
        cls, pid: int, scope_name: Optional[str] = None
    ) -> Optional[str]:
        """Applies Linux cgroup v2 limits to the given process PID."""
        return cls.cgroup_manager.setup_process_cgroup(pid, scope_name=scope_name)

    @classmethod
    def check_cgroup_v2_limits(cls, cgroup_path: Optional[str]) -> tuple[bool, str]:
        """Checks if cgroup v2 memory or process limits were breached."""
        return cls.cgroup_manager.check_limits_breached(cgroup_path)

    @classmethod
    def terminate_process_cleanly(
        cls, pid: int, cgroup_path: Optional[str] = None
    ) -> str:
        """
        Cleanly terminates a sandbox process tree and any associated cgroup v2 group,
        returning the standard informative quota exceeded message:
        "Resource quota exceeded: Memory or process limit reached"
        """
        if cgroup_path:
            cls.cgroup_manager.terminate_cgroup(cgroup_path)
        if pid:
            cls.kill_process_tree(pid)
        return cls.QUOTA_EXCEEDED_MESSAGE

    @classmethod
    def get_wrapper_script(cls, code: str) -> str:
        return f"""
import sys
try:
    import resource
    # 256MB RAM limit (memory.max = "{cls.CGROUP_MEMORY_MAX}")
    memory_limit = {cls.MAX_MEMORY_MB} * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    try:
        resource.setrlimit(resource.RLIMIT_DATA, (memory_limit, memory_limit))
    except (ValueError, OSError):
        pass
    cpu_limit = {cls.MAX_CPU_TIME_SECONDS}
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    if hasattr(resource, 'RLIMIT_NPROC'):
        # Max {cls.CGROUP_PIDS_MAX} concurrent pids (pids.max = {cls.CGROUP_PIDS_MAX})
        resource.setrlimit(resource.RLIMIT_NPROC, ({cls.CGROUP_PIDS_MAX}, {cls.CGROUP_PIDS_MAX}))
except (ImportError, Exception):
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
    print("{cls.QUOTA_EXCEEDED_MESSAGE}", file=sys.stderr)
    sys.exit(137)
except (BlockingIOError, OSError) as e:
    # Fork failure when pids limit is exceeded (Errno 11: EAGAIN / Resource temporarily unavailable)
    if "Resource temporarily unavailable" in str(e) or getattr(e, "errno", None) in (11,):
        print("{cls.QUOTA_EXCEEDED_MESSAGE}", file=sys.stderr)
        sys.exit(137)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
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
