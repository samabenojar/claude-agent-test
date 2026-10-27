import argparse
import os
import sys
import uuid
from pathlib import Path

from agent_runner.artefacts import new_run_id, write_run
from agent_runner.invoke import build_argv, run_claude
from agent_runner.result import classify
from agent_runner.workflow import load_workflow

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--cwd", type=Path, default=ROOT)
    ap.add_argument("--budget", type=float, default=1.00)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    try:
        wf = load_workflow(a.workflow, ROOT)
    except FileNotFoundError as e:
        print(f"config error: missing {e}", file=sys.stderr)
        return 3
    session_id = str(uuid.uuid4())
    argv = build_argv(wf, session_id, a.budget)
    raw = run_claude(argv, a.cwd, a.timeout, os.environ.get("CLAUDE_BIN", "claude"))
    outcome = classify(raw, wf.schema)
    run_id = new_run_id()
    out_root = Path(os.environ.get("HARNESS_RUNS_ROOT", ROOT))
    d = write_run(out_root, run_id, wf.name, session_id, argv, raw, outcome)
    print(f"run_id={run_id} exit={outcome.exit_code} result={d.relative_to(out_root) / 'result.json'}")
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
