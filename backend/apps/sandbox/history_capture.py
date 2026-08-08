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


# Regex patterns matching common bash/zsh shell prompts (e.g. "user@host:~$ git commit", "$ git status")
PROMPT_PATTERN = re.compile(
    r"(?:[\w\.\-]+@[\w\.\-]+:[~\w\/\.\-]+[\$\#]|[\$\#>])\s+(git\s+[\s\S]+?)(?=\n|$)",
    re.MULTILINE,
)

# Pattern for trailing exit codes logged by custom wrappers or script --return headers
EXIT_CODE_PATTERN = re.compile(r"\[exit_code:?\s*(\d+)\]", re.IGNORECASE)


def parse_terminal_session(log_content: Union[str, List[Dict[str, Any]]]) -> List[HistoryEvent]:
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
                events.append(
                    HistoryEvent(
                        timestamp=float(item.get("timestamp", idx * 1.0)),
                        command=str(item.get("command", "")).strip(),
                        exit_code=int(item.get("exit_code", 0)),
                        raw_output=str(item.get("raw_output", "")),
                    )
                )
            elif isinstance(item, str) and item.strip():
                events.append(
                    HistoryEvent(
                        timestamp=float(idx * 1.0),
                        command=item.strip(),
                        exit_code=0,
                        raw_output="",
                    )
                )
        return [e for e in events if e.command]

    raw_text = str(log_content)

    # Try parsing JSON array directly
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            return parse_terminal_session(data)
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
