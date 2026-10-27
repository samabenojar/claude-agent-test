"""Read-only Snowflake tool for agent workflows.

Runs fixed queries through the Snowflake CLI using the `claude_ro` connection
(key-pair auth, read-only role). Credentials live in ~/.snowflake/connections.toml,
outside the harness directory. The only caller input is an integer run id.

Output matches workflows/critical_path/fixtures/dbt_run.json.
"""
import argparse
import json
import subprocess
import sys

CONNECTION = "claude_ro"
TIMINGS_SQL = (
    "select model_name, seconds, depends_on "
    "from DBT_DEMO.META.DBT_MODEL_TIMINGS where run_id = {run_id} order by model_name"
)


def query(sql: str) -> list[dict]:
    p = subprocess.run(
        ["snow", "sql", "-c", CONNECTION, "-q", sql, "--format", "json"],
        capture_output=True, text=True, timeout=120,
    )
    if p.returncode != 0:
        sys.exit(f"snow failed (rc={p.returncode}): {p.stderr.strip()[-300:]}")
    return json.loads(p.stdout)


def timings(run_id: int) -> dict:
    rows = query(TIMINGS_SQL.format(run_id=int(run_id)))
    models = [
        {
            "name": r["MODEL_NAME"],
            "seconds": int(r["SECONDS"]),
            "depends_on": [d for d in (r["DEPENDS_ON"] or "").split(",") if d],
        }
        for r in rows
    ]
    return {"run_id": int(run_id), "status": "SUCCESS" if models else "NOT_FOUND", "models": models}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("timings")
    t.add_argument("--run-id", type=int, required=True)
    a = ap.parse_args()
    print(json.dumps(timings(a.run_id)))


if __name__ == "__main__":
    main()
