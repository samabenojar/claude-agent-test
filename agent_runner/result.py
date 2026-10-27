import json
from typing import NamedTuple

from .invoke import RawRun

_TYPES = {"string": str, "boolean": bool, "object": dict, "array": list,
          "integer": int, "number": (int, float)}


class Outcome(NamedTuple):
    exit_code: int
    payload: dict | None
    errors: list
    envelope: dict | None


def parse_envelope(stdout: str) -> dict:
    d = json.loads(stdout)
    if not isinstance(d, dict):
        raise ValueError("envelope is not an object")
    return d


def extract_payload(envelope: dict) -> dict | None:
    so = envelope.get("structured_output")
    if isinstance(so, dict):
        return so
    try:
        d = json.loads(envelope.get("result") or "")
    except (ValueError, TypeError):
        return None
    return d if isinstance(d, dict) else None


def _type_ok(v, t) -> bool:
    if t in ("integer", "number") and isinstance(v, bool):
        return False
    return isinstance(v, _TYPES[t])


def validate(payload, schema: dict) -> list:
    if not isinstance(payload, dict):
        return ["payload is not an object"]
    errs = []
    for k in schema.get("required", []):
        if k not in payload:
            errs.append(f"missing required: {k}")
    for k, spec in schema.get("properties", {}).items():
        if k not in payload:
            continue
        v = payload[k]
        t = spec.get("type")
        if t in _TYPES and not _type_ok(v, t):
            errs.append(f"{k}: expected {t}")
        elif "enum" in spec and v not in spec["enum"]:
            errs.append(f"{k}: {v!r} not in enum")
    return errs


def classify(raw: RawRun, schema: dict) -> Outcome:
    if raw.timed_out:
        return Outcome(1, None, ["timeout"], None)
    try:
        env = parse_envelope(raw.stdout)
    except ValueError as e:
        if raw.returncode != 0:
            return Outcome(1, None, [f"claude exited {raw.returncode}"], None)
        return Outcome(2, None, [f"stdout not JSON: {e}"], None)
    if raw.returncode != 0 or env.get("is_error"):
        return Outcome(1, None, [f"claude failed (rc={raw.returncode}, is_error={env.get('is_error')})"], env)
    payload = extract_payload(env)
    if payload is None:
        return Outcome(2, None, ["no payload"], env)
    errs = validate(payload, schema)
    if errs:
        return Outcome(2, payload, errs, env)
    return Outcome(0, payload, [], env)
