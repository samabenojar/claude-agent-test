import json
import subprocess
from pathlib import Path
from typing import NamedTuple

from .workflow import Workflow


class RawRun(NamedTuple):
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def build_argv(wf: Workflow, session_id: str, budget_usd: float) -> list[str]:
    """Single place defining what the agent may do."""
    argv = [
        "claude", "-p", wf.prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(wf.schema),
        "--permission-mode", "dontAsk",
    ]
    if wf.allowed_tools:
        argv += ["--allowedTools", *wf.allowed_tools]
    # Read-only tools are denied unless the workflow lists them: they can read
    # any file under cwd (keys, .env) even in dontAsk mode.
    read_tools = [t for t in ("Read", "Glob", "Grep")
                  if not any(a == t or a.startswith(t + "(") for a in wf.allowed_tools)]
    argv += [
        "--disallowedTools", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", *read_tools,
        "--setting-sources", "project",
        "--no-session-persistence",
        "--session-id", session_id,
        "--max-budget-usd", str(budget_usd),
    ]
    return argv


def run_claude(argv: list[str], cwd: Path, timeout_s: int, claude_bin: str = "claude") -> RawRun:
    cmd = [claude_bin, *argv[1:]]
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        def s(x):
            return x.decode() if isinstance(x, bytes) else (x or "")
        return RawRun(124, s(e.stdout), s(e.stderr), True)
    return RawRun(p.returncode, p.stdout, p.stderr, False)
