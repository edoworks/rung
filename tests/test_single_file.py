"""The committed standalone CLI is generated and independent of the package."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent
GENERATOR = ROOT / "scripts" / "build_single_file.py"
ARTIFACT = ROOT / "rung-cli.py"
FIXTURE = ROOT / "tests" / "fixtures" / "excellent_public_evidence"


class TestSingleFile(unittest.TestCase):
    def run_cli(self, script: Path):
        env = {**os.environ, "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run(
            [sys.executable, str(script), "--root", str(FIXTURE), "--commit-sha", "a" * 40, "--repository", "owner/repo", "--timestamp", "2026-01-01T00:00:00Z", "--json"],
            cwd=script.parent, env=env, text=True, capture_output=True, check=False,
        )

    def test_generation_is_deterministic_and_current(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.py"
            second = Path(directory) / "second.py"
            subprocess.run([sys.executable, str(GENERATOR), "--output", str(first)], check=True)
            subprocess.run([sys.executable, str(GENERATOR), "--output", str(second)], check=True)
            self.assertEqual(first.read_bytes(), second.read_bytes())
        subprocess.run([sys.executable, str(GENERATOR), "--check"], check=True)

    def test_standalone_matches_modular_output(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "rung-cli.py"
            shutil.copyfile(ARTIFACT, copied)
            standalone = self.run_cli(copied)
        modular = subprocess.run(
            [sys.executable, "-m", "rung", "--root", str(FIXTURE), "--commit-sha", "a" * 40, "--repository", "owner/repo", "--timestamp", "2026-01-01T00:00:00Z", "--json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(standalone.returncode, modular.returncode)
        standalone_data = json.loads(standalone.stdout)
        modular_data = json.loads(modular.stdout)
        for data in (standalone_data, modular_data):
            data.pop("timestamp", None)
            data.pop("report_data_sha256", None)
        self.assertEqual(standalone_data, modular_data)

    def test_commit_sha_rejects_noncanonical_values(self):
        result = subprocess.run(
            [sys.executable, str(ARTIFACT), "--root", str(FIXTURE), "--commit-sha", "not-a-sha", "--json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("40 lowercase hex", result.stderr)


if __name__ == "__main__":
    unittest.main()
