import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class HistoryEvent:
    """Represents a single command execution event captured during a terminal session."""

    timestamp: float
    command: str
    exit_code: int = 0
    raw_output: str = ""
    stdout: str = ""
    stderr: str = ""
    is_truncated: bool = False


# Regex patterns matching common bash/zsh shell prompts (e.g. "user@host:~$ git commit", "$ git status")
PROMPT_PATTERN = re.compile(
    r"(?:[\w\.\-]+@[\w\.\-]+:[~\w\/\.\-]+[\$\#]|[\$\#>])\s+(git\s+[\s\S]+?)(?=\n|$)",
    re.MULTILINE,
)

# Pattern for trailing exit codes logged by custom wrappers or script --return headers
EXIT_CODE_PATTERN = re.compile(r"\[exit_code:?\s*(\d+)\]", re.IGNORECASE)


def parse_terminal_session(
    log_content: Union[str, List[Dict[str, Any]]],
    max_output_length: Optional[int] = None,
) -> List[HistoryEvent]:
    """
    Parses a raw terminal session log or typescript stream into a chronological list of HistoryEvent objects.
    Supports both JSON-structured command arrays and raw text shell outputs.
    """
    if not log_content:
        return []

    # If log_content is already a parsed list of dicts
    if isinstance(log_content, list):
        events: List[HistoryEvent] = []
        for idx, item in enumerate(log_content):
            if isinstance(item, dict):
                cmd = str(item.get("command", "")).strip()
                raw_out = str(item.get("raw_output", ""))
                stdout_val = str(
                    item.get("stdout", raw_out if "stderr" not in item else "")
                )
                stderr_val = str(item.get("stderr", ""))

                is_trunc = False
                if max_output_length is not None:
                    from apps.sandbox.telemetry import truncate_sandbox_output

                    if stdout_val:
                        stdout_val, trunc_s = truncate_sandbox_output(
                            stdout_val,
                            stream="stdout",
                            command=cmd,
                            limit=max_output_length,
                        )
                        is_trunc = is_trunc or trunc_s

                    if stderr_val:
                        stderr_val, trunc_e = truncate_sandbox_output(
                            stderr_val,
                            stream="stderr",
                            command=cmd,
                            limit=max_output_length,
                        )
                        is_trunc = is_trunc or trunc_e

                    if raw_out and not item.get("stdout") and not item.get("stderr"):
                        raw_out, trunc_r = truncate_sandbox_output(
                            raw_out,
                            stream="stdout",
                            command=cmd,
                            limit=max_output_length,
                        )
                        is_trunc = is_trunc or trunc_r
                        stdout_val = raw_out

                events.append(
                    HistoryEvent(
                        timestamp=float(item.get("timestamp", idx * 1.0)),
                        command=cmd,
                        exit_code=int(item.get("exit_code", 0)),
                        raw_output=raw_out,
                        stdout=stdout_val,
                        stderr=stderr_val,
                        is_truncated=is_trunc,
                    )
                )
            elif isinstance(item, str) and item.strip():
                cmd_str = item.strip()
                events.append(
                    HistoryEvent(
                        timestamp=float(idx * 1.0),
                        command=cmd_str,
                        exit_code=0,
                        raw_output="",
                        stdout="",
                        stderr="",
                        is_truncated=False,
                    )
                )
        return [e for e in events if e.command]

    raw_text = str(log_content)

    # Try parsing JSON array directly
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            return parse_terminal_session(data, max_output_length=max_output_length)
    except (json.JSONDecodeError, TypeError):
        pass

    # Process plain text typescript / script log output
    events = []
    lines = raw_text.splitlines()
    current_time = time.time()

    for idx, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean:
            continue

        # Check for explicit prompt matches
        match = PROMPT_PATTERN.search(line_clean)
        if match:
            cmd = match.group(1).strip()
            # Clean up escape codes / control chars if any
            cmd = re.sub(r"\x1b\[[0-9;]*[mK]", "", cmd)
            events.append(
                HistoryEvent(
                    timestamp=current_time + (idx * 0.5),
                    command=cmd,
                    exit_code=0,
                    raw_output=line_clean,
                )
            )
            continue

        # Direct 'git' command line
        if line_clean.startswith("git "):
            cmd = re.sub(r"\x1b\[[0-9;]*[mK]", "", line_clean)
            exit_code = 0
            exit_match = EXIT_CODE_PATTERN.search(cmd)
            if exit_match:
                exit_code = int(exit_match.group(1))
                cmd = EXIT_CODE_PATTERN.sub("", cmd).strip()

            events.append(
                HistoryEvent(
                    timestamp=current_time + (idx * 0.5),
                    command=cmd,
                    exit_code=exit_code,
                    raw_output=line_clean,
                )
            )

    return events
