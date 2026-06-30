import ast
import logging
import sys

from django.contrib.auth import get_user_model
from django.core.cache import cache

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
    }
    FORBIDDEN_FUNCTIONS = {"open", "eval", "exec", "__import__"}

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
            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in cls.FORBIDDEN_FUNCTIONS
                ):
                    raise SecurityViolation(
                        f"Function call '{node.func.id}()' is disabled in the sandbox."
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
safe_globals = {{"__builtins__": {{k: v for k, v in __builtins__.items() if k not in {cls.FORBIDDEN_FUNCTIONS}}}}}

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
