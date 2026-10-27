"""Compare persisted dbt outputs, including duplicate multiplicity. Stdlib only."""
import argparse
import json
import subprocess
from pathlib import Path

MODELS = ("int_transactions", "fct_transactions", "rpt_finance")


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def query(connection, sql):
    p = subprocess.run(
        ["snow", "sql", "-c", connection, "-q", sql, "--format", "json"],
        capture_output=True, text=True, timeout=120,
    )
    if p.returncode:
        raise RuntimeError(f"Snowflake query failed: {p.stderr[-1500:]}")
    return json.loads(p.stdout)


def model(manifest, name, expected_schema):
    matches = [n for n in manifest["nodes"].values()
               if n.get("resource_type") == "model" and n["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one model {name}, found {len(matches)}")
    n = matches[0]
    quoting = n["config"].get("quoting", {})
    # Snowflake folds unquoted dbt aliases to uppercase. Quoting a lowercase
    # manifest alias verbatim would incorrectly address a different relation.
    values = [n["database"], n["schema"], n["alias"]]
    names = [v if quoting.get(k, False) else v.upper()
             for k, v in zip(("database", "schema", "identifier"), values)]
    if names[0] != "DBT_DEMO" or names[1] != expected_schema:
        raise ValueError(f"{name}: unexpected output location {names[:2]}")
    return names, ".".join(ident(v) for v in names)


def columns(connection, names):
    db, schema, alias = names
    rows = query(connection, f"""
        select column_name, data_type, character_maximum_length,
               numeric_precision, numeric_scale, datetime_precision
        from {ident(db)}.information_schema.columns
        where table_schema = {literal(schema)} and table_name = {literal(alias)}
        order by ordinal_position
    """)
    if not rows:
        raise ValueError(f"No column metadata found for {names}")
    return rows


def metrics(connection, relation, names):
    nulls = ", ".join(f"coalesce(count_if({ident(c)} is null), 0) as C{i}"
                      for i, c in enumerate(names))
    row = query(connection, f"select count(*) as N, {nulls} from {relation}")[0]
    cols = ", ".join(ident(c) for c in names)
    duplicates = query(connection, f"""
        select coalesce(sum(n - 1), 0) as N from (
            select count(*) as n from {relation} group by {cols}
        )
    """)[0]["N"]
    return {"row_count": int(row["N"]), "duplicate_rows": int(duplicates),
            "null_counts": {c: int(row[f"C{i}"]) for i, c in enumerate(names)}}


def mismatches(connection, baseline, candidate, names):
    cols = ", ".join(ident(c) for c in names)
    # MINUS is set-based, so include each full row's multiplicity before
    # comparing both directions. NULL rows participate in set equality.
    return int(query(connection, f"""
        with b as (select {cols}, count(*) as __row_count
                   from {baseline} group by {cols}),
             c as (select {cols}, count(*) as __row_count
                   from {candidate} group by {cols}),
             b_only as (select * from b minus select * from c),
             c_only as (select * from c minus select * from b)
        select (select count(*) from b_only) +
               (select count(*) from c_only) as N
    """)[0]["N"])


def compare(connection, baseline, candidate, baseline_schema, candidate_schema):
    if baseline_schema == candidate_schema:
        raise ValueError("Baseline and candidate schemas must differ")
    result = {"status": "PASS", "models": {}}
    for name in MODELS:
        bn, br = model(baseline, name, baseline_schema)
        cn, cr = model(candidate, name, candidate_schema)
        bc, cc = columns(connection, bn), columns(connection, cn)
        row = {"baseline_relation": br, "candidate_relation": cr,
               "schema_match": bc == cc}
        if bc != cc:
            row.update(status="FAIL", baseline_columns=bc, candidate_columns=cc)
        else:
            names = [c["COLUMN_NAME"] for c in bc]
            bm, cm = metrics(connection, br, names), metrics(connection, cr, names)
            count = mismatches(connection, br, cr, names)
            row.update(baseline=bm, candidate=cm, mismatched_row_groups=count,
                       status="PASS" if bm == cm and count == 0 else "FAIL")
        result["models"][name] = row
        if row["status"] != "PASS":
            result["status"] = "FAIL"
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--baseline-schema", required=True)
    ap.add_argument("--candidate-schema", required=True)
    ap.add_argument("--connection", default="dbt_dev")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--baseline-sha", required=True)
    ap.add_argument("--candidate-sha", required=True)
    a = ap.parse_args()
    try:
        result = compare(a.connection, json.loads(a.baseline.read_text()),
                         json.loads(a.candidate.read_text()),
                         a.baseline_schema, a.candidate_schema)
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        result = {"status": "ERROR", "errors": [str(e)]}
    result.update(baseline_sha=a.baseline_sha, candidate_sha=a.candidate_sha)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
