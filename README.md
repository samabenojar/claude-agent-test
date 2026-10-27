# claude -p harness

Runs `claude -p` headless with a bounded objective, a tool allowlist, a JSON schema, and a deterministic exit code. Python stdlib only.

## Run

    python3 run.py smoke                 # runner validation
    python3 run.py critical_path         # fixture-backed dbt critical path recommendation
    python3 run.py snowflake_profile     # same objective, data read live from Snowflake (read-only role)
    python3 run.py <workflow> [--cwd PATH] [--budget USD] [--timeout SEC]

Final stdout line: `run_id=<id> exit=<n> result=<path>`. Artefacts land in `runs/<run_id>/` (`argv.json`, `stdout.json`, `stderr.txt`, `result.json`, `summary.json`).

Tests (fake claude, no API calls): `python3 -m unittest discover -s tests -v`

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Completed with schema-valid payload. Recommendation is on disk; stop for human. |
| 1 | claude failed: nonzero return, `is_error`, budget exhausted, or timeout. |
| 2 | claude ran but payload missing or schema-invalid. |
| 3 | Config error (workflow folder or file missing). |

## Safety

All flags live in `agent_runner/invoke.py:build_argv`: `--permission-mode dontAsk`, an explicit `--allowedTools` list per workflow, write/web tools disallowed, `--max-budget-usd`, and a subprocess timeout. No `--bare`, no `bypassPermissions`. `--max-turns` is not used (absent from `claude --help` in 2.1.308).

`Read`, `Glob`, and `Grep` are also disallowed unless a workflow lists them.

**Permission rules are a guardrail, not a security boundary.** Claude Code auto-approves built-in read-only shell commands inside `--cwd` regardless of the `Bash(...)` allowlist. Tested on 2.1.308 with the exact `critical_path` argv: `cat probe.env` inside `--cwd` returned the file; `cat` outside `--cwd` was denied. `printenv VAR`, `env`, `echo $VAR`, and `cat /proc/self/environ` were all denied in the same setup, but treat that as observed behaviour of this version, not a guarantee. Rules:

1. Never place credentials (private key, `.env`, tokens) under `--cwd`.
2. Environment variables set for `run.py` are inherited by `claude` and its shell commands. Do not rely on env vars to hide secrets from the agent. Prefer a credential file outside `--cwd`, readable only by the tool's identity (separate OS user via `sudo -u`, or a secret store the agent's user cannot read).
3. Enforce least privilege at the target system (read-only Snowflake role, scoped dbt token). That is the control that holds if the permission rules fail. Verify it with real write probes, not one refused `CREATE DATABASE`: every role inherits `PUBLIC`, and on the trial account `PUBLIC` was granted `SNOWFLAKE_LEARNING_ROLE`, which let `CLAUDE_READONLY` create schemas and tables until it was revoked. Check `SHOW GRANTS TO ROLE PUBLIC`, then try `CREATE SCHEMA`, `CREATE TABLE`, `INSERT`, and `DELETE`. Known residual: with only `USAGE` on a schema, the role can still create session-scoped `TEMPORARY` tables. They vanish when the session ends and touch no persisted data.

## Snowflake setup (`snowflake_profile`)

Connection `claude_ro` in `~/.snowflake/connections.toml` (outside `--cwd`, `chmod 600`): key-pair auth (`SNOWFLAKE_JWT`) for a `TYPE = SERVICE` user `CLAUDE_SVC`, role `CLAUDE_READONLY`, warehouse `CLAUDE_WH`. `tools/snowflake_ro.py` runs one fixed query through `snow sql -c claude_ro`; its only input is an integer run id. The source table has no status column, so the tool reports `SUCCESS` when rows exist and `NOT_FOUND` otherwise. Data: `DBT_DEMO.META.DBT_MODEL_TIMINGS`, loaded with the same five models as the `critical_path` fixture.

## Adding a workflow

Create `workflows/<name>/` with `workflow.json` (`{"allowed_tools": [...]}`), `prompt.md`, `schema.json`. The hand-rolled validator supports only `type`, `required`, `properties` primitive `type`, and `enum`.

## Future seams

- Real dbt Cloud API: add `tools/dbt_api.py` and list it in `allowed_tools`. Use a scoped read-only token, read from a credential file outside `--cwd` that only the tool's identity can read (see Safety rule 2).
- Snowflake profiling: read-only role CLI under `tools/`, listed in a new workflow's `allowed_tools`. Key-pair auth on a `TYPE = SERVICE` user; private key outside `--cwd`.
- Edits, dbt build, parity: a later workflow with a working-branch `--cwd` and a narrower write allowlist, still ending in exit 0 and stop for human.
- JAMS/VM wrapper: a job step that installs Claude Code, exports `ANTHROPIC_API_KEY`, runs `python3 run.py <workflow> --cwd <checkout>`, and branches on the exit code. VM auth is untested here.
- VM discard: delete the VM after collecting `runs/<run_id>/`.
