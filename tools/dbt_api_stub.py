"""Stands in for the dbt Cloud API: prints fixture data. --run-id is accepted and ignored."""
import argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--run-id")
ap.parse_args()
print((Path(__file__).resolve().parent.parent / "workflows/critical_path/fixtures/dbt_run.json").read_text())
