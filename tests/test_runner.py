import json
import os
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent_runner.invoke import RawRun, build_argv  # noqa: E402
from agent_runner.result import classify  # noqa: E402
from agent_runner.workflow import load_workflow  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def env_text(**over):
    d = json.loads((FIX / "envelope_schema.json").read_text())
    d.update(over)
    return json.dumps(d)


class Argv(unittest.TestCase):
    def test_safety_flags(self):
        names = sorted(p.name for p in (ROOT / "workflows").iterdir() if p.is_dir())
        self.assertGreaterEqual(len(names), 3)
        for name in names:
            a = build_argv(load_workflow(name, ROOT), "sid", 1.0)
            for bad in ("--bare", "--dangerously-skip-permissions", "bypassPermissions"):
                self.assertNotIn(bad, a)
            self.assertIn("dontAsk", a)
            for t in ("Write", "Edit", "NotebookEdit"):
                self.assertIn(t, a[a.index("--disallowedTools"):])

    def test_read_tools_denied_unless_allowlisted(self):
        from dataclasses import replace
        wf = load_workflow("smoke", ROOT)
        denied = lambda w: build_argv(w, "sid", 1.0)[build_argv(w, "sid", 1.0).index("--disallowedTools"):]
        for t in ("Read", "Glob", "Grep"):
            self.assertIn(t, denied(wf))
        self.assertNotIn("Read", denied(replace(wf, allowed_tools=["Read"])))
        self.assertIn("Grep", denied(replace(wf, allowed_tools=["Read"])))


class Classify(unittest.TestCase):
    def test_valid(self):
        o = classify(RawRun(0, (FIX / "envelope_schema.json").read_text(), "", False), SCHEMA)
        self.assertEqual(o.exit_code, 0)

    def test_schema_violation(self):
        o = classify(RawRun(0, env_text(structured_output={"ok": "yes"}), "", False), SCHEMA)
        self.assertEqual(o.exit_code, 2)

    def test_is_error(self):
        self.assertEqual(classify(RawRun(0, env_text(is_error=True), "", False), SCHEMA).exit_code, 1)

    def test_timeout(self):
        self.assertEqual(classify(RawRun(124, "", "", True), SCHEMA).exit_code, 1)

    def test_junk(self):
        self.assertEqual(classify(RawRun(0, "not json", "", False), SCHEMA).exit_code, 2)


class EndToEnd(unittest.TestCase):
    def run_it(self, runs_root, **extra):
        env = {**os.environ, "CLAUDE_BIN": str(ROOT / "tests/fake_claude.sh"),
               "HARNESS_RUNS_ROOT": runs_root, **extra}
        return subprocess.run([sys.executable, "run.py", "smoke"], cwd=ROOT, env=env,
                              capture_output=True, text=True)

    def test_exit_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.run_it(tmp, FAKE_ENVELOPE=str(FIX / "envelope_schema.json"))
            # fixture payload {"ok": true} violates smoke schema -> 2
            self.assertEqual(p.returncode, 2, p.stderr)
            run_id = p.stdout.split("run_id=")[1].split()[0]
            s = json.loads((Path(tmp) / "runs" / run_id / "summary.json").read_text())
            self.assertEqual(s["exit_code"], 2)

    def test_claude_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.run_it(tmp, FAKE_ENVELOPE=str(FIX / "envelope_ok.json"), FAKE_RC="1")
            self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
