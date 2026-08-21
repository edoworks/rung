"""Cross-process determinism regressions."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent


class HashSeedDeterminismTest(unittest.TestCase):
    def test_multi_command_audit_digest_is_hash_seed_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            (fixture / "AGENTS.md").write_text(
                "# Build\nRun npm test, make build, python3 -m unittest, and cargo test.\n",
                encoding="utf-8",
            )
            (fixture / "Makefile").write_text("build:\n\t@true\n", encoding="utf-8")
            script = (
                "import json,sys; from pathlib import Path; "
                "from rung.audit import run_audit; "
                "r=run_audit(Path(sys.argv[1]),commit_sha='a'*40,"
                "repository='github.com/example/project',timestamp='2026-01-01T00:00:00Z'); "
                "print(json.dumps({'digest':r.report_data_sha256,"
                "'evidence':r.checks[1].evidence},sort_keys=True))"
            )
            outputs = []
            for seed in ("1", "7", "42", "random"):
                result = subprocess.run(
                    [sys.executable, "-c", script, str(fixture)], cwd=ROOT,
                    env={**os.environ, "PYTHONHASHSEED": seed}, text=True,
                    capture_output=True, check=True,
                )
                outputs.append(result.stdout)
            self.assertTrue(all(output == outputs[0] for output in outputs))
            self.assertGreater(len(json.loads(outputs[0])["evidence"][0].split(",")), 1)


if __name__ == "__main__":
    unittest.main()
