import ast
import logging
import time
import sys
import redis

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

from apps.sandbox.models import ExecutionViolationLog

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    pass


class ResourceManagementEngine:
    MAX_EXECUTION_TIME_SECONDS = 5
    MAX_MEMORY_MB = 128
    MAX_CPU_TIME_SECONDS = 3
    MAX_CONCURRENT_EXECUTIONS = 2

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
    def acquire_execution_lock(cls, session_id: str) -> bool:
        cache_key = f"sandbox_concurrent_executions_{session_id}"
        current = cache.get(cache_key, 0)

        if current >= cls.MAX_CONCURRENT_EXECUTIONS:
            return False

        cache.set(cache_key, current + 1, timeout=cls.MAX_EXECUTION_TIME_SECONDS * 2)
        return True

    @classmethod
    def release_execution_lock(cls, session_id: str):
        cache_key = f"sandbox_concurrent_executions_{session_id}"
        current = cache.get(cache_key, 0)

        if current > 0:
            cache.set(
                cache_key, current - 1, timeout=cls.MAX_EXECUTION_TIME_SECONDS * 2
            )


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
