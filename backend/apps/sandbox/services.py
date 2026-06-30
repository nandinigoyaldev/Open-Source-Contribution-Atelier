from dataclasses import dataclass

ALLOWED_PREFIXES = (
    "git status",
    "git init",
    "git add",
    "git commit",
    "git branch",
    "git checkout",
    "git switch",
    "git merge",
    "git pull",
    "git push",
    "git clone",
    "git remote",
    "git log",
)


from .linter import lint_command


@dataclass
class VerificationResult:
    accepted: bool
    feedback: str
    score_delta: int


def verify_git_command(command: str, expected_command: str) -> VerificationResult:
    normalized = command.strip()
    expected = expected_command.strip()

    # Perform syntax checking / linting before validation
    lint_result = lint_command(normalized)
    if not lint_result.is_valid:
        return VerificationResult(
            accepted=False,
            feedback=lint_result.message,
            score_delta=0,
        )

    if not any(normalized.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return VerificationResult(
            accepted=False,
            feedback="That command is outside the safe learning sandbox. Try a Git command from the lesson prompt.",
            score_delta=0,
        )

    if normalized == expected:
        return VerificationResult(
            accepted=True,
            feedback="Correct command. Nice work progressing through the workflow.",
            score_delta=10,
        )

    return VerificationResult(
        accepted=False,
        feedback=f"Valid Git syntax, but not the expected command for this exercise. Hint: Try '{expected}'.",
        score_delta=0,
    )


import asyncio
import sys
import os
import tempfile
import json


import asyncio
import sys
from .resource_manager import ResourceManagementEngine, SecurityViolation

async def stream_python_execution(code: str, send_callback, user_id: str = "anonymous", timeout: int = ResourceManagementEngine.MAX_EXECUTION_TIME_SECONDS):
    """
    Executes Python code securely with resource limits in a subprocess and streams output asynchronously.
    """
    if not ResourceManagementEngine.acquire_execution_lock(user_id):
        from asgiref.sync import sync_to_async
        await sync_to_async(ResourceManagementEngine.log_violation)(user_id, code, "concurrency", "Exceeded concurrent executions limit.")
        await send_callback({"action": "execution_error", "error": "Execution limit reached. Please wait for your previous code to finish."})
        return

    try:
        # 1. AST Static Security Analysis
        try:
            ResourceManagementEngine.analyze_ast(code)
        except SecurityViolation as sv:
            from asgiref.sync import sync_to_async
            await sync_to_async(ResourceManagementEngine.log_violation)(user_id, code, "security", str(sv))
            await send_callback({"action": "execution_error", "error": f"Security Violation: {sv}"})
            return

        await send_callback({"action": "execution_start"})

        wrapper_code = ResourceManagementEngine.get_wrapper_script(code)
        
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            wrapper_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def read_stream(stream, stream_type):
            while True:
                line = await stream.readline()
                if line:
                    await send_callback(
                        {
                            "action": "execution_output",
                            "type": stream_type,
                            "output": line.decode("utf-8", errors="replace"),
                        }
                    )
                else:
                    break

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, "stdout"),
                    read_stream(process.stderr, "stderr"),
                    process.wait(),
                ),
                timeout=timeout,
            )

            status = "Completed"
            if process.returncode == 137:
                status = "Memory Limit Exceeded"
                from asgiref.sync import sync_to_async
                await sync_to_async(ResourceManagementEngine.log_violation)(user_id, code, "memory", "Process returned 137")
            elif process.returncode != 0:
                status = "Failed"

            await send_callback(
                {
                    "action": "execution_end",
                    "status": status,
                    "returncode": process.returncode,
                }
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            from asgiref.sync import sync_to_async
            await sync_to_async(ResourceManagementEngine.log_violation)(user_id, code, "timeout", "Execution exceeded time limit")
            await send_callback(
                {"action": "execution_end", "status": "Timed Out (CPU/Time Limit Exceeded)", "returncode": -1}
            )

    except Exception as e:
        await send_callback({"action": "execution_error", "error": str(e)})
    finally:
        ResourceManagementEngine.release_execution_lock(user_id)


async def start_debug_session(code: str, breakpoints: list):
    """
    Starts a debugging session by writing code to a temp file and launching debugger_script.py
    Returns the subprocess and the temp file path.
    """
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(code)
    
    debugger_script = os.path.join(os.path.dirname(__file__), "debugger_script.py")
    
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        debugger_script,
        path,
        json.dumps(breakpoints),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    return process, path
