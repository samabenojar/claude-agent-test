import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .invoke import RawRun
from .result import Outcome


def new_run_id() -> str:
    return f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


def write_run(root: Path, run_id: str, workflow: str, session_id: str,
              argv: list, raw: RawRun, outcome: Outcome) -> Path:
    d = root / "runs" / run_id
    d.mkdir(parents=True)  # raises if exists
    (d / "argv.json").write_text(json.dumps(argv, indent=2))
    (d / "stdout.json").write_text(raw.stdout)
    (d / "stderr.txt").write_text(raw.stderr)
    result = outcome.payload if outcome.exit_code == 0 else {"errors": outcome.errors}
    (d / "result.json").write_text(json.dumps(result, indent=2))
    summary = {"run_id": run_id, "workflow": workflow,
               "exit_code": outcome.exit_code, "session_id": session_id}
    if outcome.errors:
        summary["errors"] = outcome.errors
    env = outcome.envelope or {}
    for src, dst in (("total_cost_usd", "cost_usd"), ("duration_ms", "duration_ms")):
        if src in env:
            summary[dst] = env[src]
    (d / "summary.json").write_text(json.dumps(summary, indent=2))
    return d
