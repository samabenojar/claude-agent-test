Objective: recommend the single dbt model on the critical path most worth optimising.

1. Get the run with exactly: python3 tools/snowflake_ro.py timings --run-id 847293
2. Compute the critical path: the dependency chain (via depends_on) with the largest summed seconds.
3. Rank the models on that path by seconds and recommend the top one.
4. Do not write files. Do not run any other command.
5. If the run status is not SUCCESS, return status "no_candidate".

Return the JSON object requested by the schema. critical_path is the ordered list of model names; dbt_run_id is the integer run id; reason is one sentence; next_action is one sentence for a human reviewer.
