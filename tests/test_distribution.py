"""Distribution contract tests that do not require registry credentials."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent


class DistributionContractTest(unittest.TestCase):
    def test_manifest_distinguishes_available_and_planned_channels(self):
        manifest = json.loads((ROOT / "product-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["owner"], "Foculoom LLC")
        self.assertEqual(manifest["builder"], "Edoworks")
        channels = {channel["id"]: channel["status"] for channel in manifest["channels"]}
        self.assertEqual(channels["website"], "available")
        self.assertEqual(channels["pypi"], "planned")
        self.assertEqual(channels["skills-sh"], "planned")
        self.assertEqual(manifest["evidence"]["external_adoption"], "unverified")

    def test_skill_mirror_is_generated_from_canonical_project_skill(self):
        subprocess.run([sys.executable, "scripts/sync_skill.py", "--check"], cwd=ROOT, check=True)
        canonical = ROOT / ".agents" / "skills" / "rung-reproducible-verification" / "SKILL.md"
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / ".agents" / "skills" / "rung-reproducible-verification"
            installed.parent.mkdir(parents=True)
            shutil.copytree(canonical.parent, installed)
            skill = (installed / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: rung-reproducible-verification\n"))
        self.assertIn("independently installed, version-pinned `rung`", skill)
        self.assertIn("must not be rewritten to appear successful", " ".join(skill.split()))

    def test_distribution_validator_and_action_contract_pass(self):
        subprocess.run([sys.executable, "scripts/validate_distribution.py"], cwd=ROOT, check=True)
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertNotIn("contents: write", action)
        self.assertNotIn("pulls: write", action)
        self.assertIn('python3 "$GITHUB_ACTION_PATH/rung-cli.py"', action)
        self.assertIn("RUNG_REQUIRE_GATE", action)
        self.assertIn("relative_to(workspace)", action)
        self.assertIn("root must not contain symlinks", action)
        self.assertIn("contains a control character", action)
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("--require-hashes -r requirements-release.txt", workflow)
        self.assertIn("python -m build --no-isolation", workflow)
        self.assertIn("SOURCE_DATE_EPOCH", workflow)
        self.assertIn("diff -r dist/packages-a dist/packages-b", workflow)
        self.assertIn("normalize_sdist.py --dist dist/packages-a", workflow)


if __name__ == "__main__":
    unittest.main()
