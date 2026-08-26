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
        self.assertIn("python scripts/validate_release.py --dist dist", workflow)
        release_validator = (ROOT / "scripts" / "validate_release.py").read_text(encoding="utf-8")
        for required in (
            "SOURCE_DATE_EPOCH",
            '"-m", "build", "--no-isolation"',
            "normalize_sdist.py",
            "compare_trees(build_a, build_b)",
            "release_artifacts.py",
            '"--no-deps"',
            '"--no-index"',
            '"PYTHONPATH"',
            'for name in ("wheel.json", "modular.json", "standalone.json")',
        ):
            self.assertIn(required, release_validator)
        self.assertIn("pull_request:", workflow)
        self.assertIn("release-gate:", workflow)
        self.assertIn("needs: [test, build]", workflow)
        self.assertIn('test "$TEST_RESULT" = success && test "$BUILD_RESULT" = success', workflow)

    def test_package_metadata_has_canonical_public_urls(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('description = "Assess observable repository evidence for responsible AI coding-agent authority"', pyproject)
        self.assertIn('readme = "README.md"', pyproject)
        self.assertIn('Homepage = "https://rung.edoworks.com/"', pyproject)
        self.assertIn('Repository = "https://github.com/edoworks/rung"', pyproject)
        self.assertIn('Issues = "https://github.com/edoworks/rung/issues"', pyproject)
        self.assertIn('Changelog = "https://github.com/edoworks/rung/releases"', pyproject)

    def test_first_release_notes_preserve_authority_and_commercial_limits(self):
        notes = (ROOT / "docs" / "releases" / "v0.3.1.md").read_text(encoding="utf-8")
        self.assertIn("public repository evidence", notes)
        self.assertIn("not certification", notes)
        self.assertIn("paid report is not launched", notes)
        self.assertNotIn("external adoption", notes.lower())
        self.assertIn(
            "does not establish that any registry or release channel completed publication",
            " ".join(notes.split()),
        )

    def test_release_is_serialized_main_bound_and_uses_reviewed_notes(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("group: release", workflow)
        self.assertIn("release tag must be strict vMAJOR.MINOR.PATCH", workflow)
        self.assertIn("release tag must bind the exact current origin/main revision", workflow)
        self.assertIn("name: release", workflow)
        self.assertIn("body_path: dist/release-notes.md", workflow)
        self.assertIn("fail_on_unmatched_files: true", workflow)
        self.assertIn("remote release tag moved after build", workflow)
        self.assertIn("reviewed main moved after release build", workflow)
        self.assertIn("release tag must be annotated", workflow)

    def test_release_validator_rejects_output_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "scripts/validate_release.py", "--dist", directory],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the repository", result.stderr)

    def test_release_validator_preserves_unknown_output_content(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            marker = Path(directory) / "keep.txt"
            marker.write_text("not a release artifact\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/validate_release.py", "--dist", directory],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertTrue(marker.is_file())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown dist content", result.stderr)

    def test_release_checksums_include_sbom(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            (dist / "artifact.txt").write_text("release artifact\n", encoding="utf-8")
            subprocess.run(
                [sys.executable, "scripts/release_artifacts.py", "--dist", directory],
                cwd=ROOT,
                check=True,
            )
            checksums = (dist / "checksums.txt").read_text(encoding="utf-8")
        self.assertIn("  artifact.txt\n", checksums)
        self.assertIn("  sbom.cdx.json\n", checksums)


if __name__ == "__main__":
    unittest.main()
