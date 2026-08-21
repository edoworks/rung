"""Reproducible receipt and independent replay behavior."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from unittest import mock

from rung.audit import run_audit
from rung.git_snapshot import SnapshotError, load_commit
import rung.verification as verification
from rung.verification import (
    MAX_JSON_BYTES,
    VerificationError,
    canonical_json,
    create_receipt,
    replay_receipt,
    normalize_repository,
    inspect_checkout,
)


ROOT = Path(__file__).parent.parent
ARTIFACT = ROOT / "rung-cli.py"


class VerificationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.source = self.base / "source"
        self._make_repository(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def _git(self, root: Path, *args: str, env=None) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args], text=True, capture_output=True,
            check=True, env=env,
        )
        return result.stdout.strip()

    def _make_repository(self, root: Path, name="Example/Project"):
        root.mkdir()
        self._git(root, "init", "-q")
        self._git(root, "config", "user.name", "Rung Test")
        self._git(root, "config", "user.email", "rung@example.invalid")
        (root / "AGENTS.md").write_text(
            "# Agent policy\nRun python3 -m unittest before commit.\n"
            "Never commit secrets. Require independent review before commit.\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        workflow = root / ".github" / "workflows"
        workflow.mkdir(parents=True)
        (workflow / "test.yml").write_text(
            "name: test\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: python3 -m unittest\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-01-02T03:04:05Z",
            "GIT_COMMITTER_DATE": "2026-01-02T03:04:05Z",
        }
        self._git(root, "commit", "-q", "-m", "fixture", env=env)
        self._git(root, "remote", "add", "origin", f"git@github.com:{name}.git")

    def _clone(self, name: str, repository="https://github.com/example/project.git") -> Path:
        clone = self.base / name
        subprocess.run(
            ["git", "clone", "-q", str(self.source), str(clone)], check=True
        )
        self._git(clone, "remote", "set-url", "origin", repository)
        return clone

    def _receipt(self, root=None, name="receipt.json") -> tuple[Path, dict]:
        path = self.base / name
        value = create_receipt(root or self.source, path)
        self.assertEqual(path.read_bytes(), canonical_json(value))
        return path, value

    def _rewrite(self, path: Path, value: dict):
        value["argv"] = [
            "rung", "--root", "{checkout}", "--commit-sha", value["commit_sha"],
            "--repository", value["repository"], "--timestamp",
            value["commit_timestamp"], "--json",
        ]
        unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
        value["receipt_sha256"] = hashlib.sha256(canonical_json(unsigned)).hexdigest()
        path.write_bytes(canonical_json(value))

    def test_verify_and_cross_directory_replay_are_reproducible(self):
        first = self._clone("first", "https://GitHub.com/Example/Project.git")
        second = self._clone("second", "ssh://git@github.com/EXAMPLE/PROJECT.git")
        receipt_path, receipt = self._receipt(first)
        second_receipt, _ = self._receipt(second, "second-receipt.json")
        self.assertEqual(receipt_path.read_bytes(), second_receipt.read_bytes())

        before = receipt_path.read_bytes()
        observation_path = self.base / "observation.json"
        observation, matched = replay_receipt(second, receipt_path, observation_path)
        self.assertTrue(matched)
        self.assertTrue(observation["matched"])
        self.assertEqual(observation["mismatch_categories"], [])
        self.assertEqual(receipt_path.read_bytes(), before)
        self.assertEqual(receipt["repository"], "github.com/example/project")
        self.assertEqual(observation["authority"], receipt["authority"])
        self.assertEqual(observation_path.read_bytes(), canonical_json(observation))
        audit = run_audit(first)
        self.assertIn("unobservable", [check.state.value for check in audit.checks])

    def test_each_critical_mismatch_is_bounded_and_deterministic(self):
        cases = {
            "engine": ("engine_artifact_sha256", "f" * 64),
            "repository": ("repository", "github.com/other/project"),
            "commit": ("commit_sha", "b" * 40),
            "tree": ("tree_sha", "c" * 40),
            "commit_timestamp": ("commit_timestamp", "2025-01-01T00:00:00Z"),
            "audit_schema": ("audit_result_schema", "9.9.9"),
            "audit_digest": ("audit_result_sha256", "d" * 64),
            "quality_gate": ("quality_gate", None),
            "authority": ("authority", "unsafe"),
        }
        for category, (field, replacement) in cases.items():
            with self.subTest(category=category):
                receipt_path, original = self._receipt(name=f"{category}.json")
                changed = dict(original)
                if category == "quality_gate":
                    replacement = "FAIL" if original[field] == "PASS" else "PASS"
                if category == "authority" and original[field] == replacement:
                    replacement = "local_only"
                changed[field] = replacement
                self._rewrite(receipt_path, changed)
                observation, matched = replay_receipt(
                    self.source, receipt_path, self.base / f"{category}-observation.json"
                )
                self.assertFalse(matched)
                self.assertEqual(observation["mismatch_categories"], [category])

    def test_malformed_receipts_write_no_observation(self):
        receipt_path, receipt = self._receipt()
        malformed = {
            "unknown": canonical_json({**receipt, "unexpected": True}),
            "duplicate": b'{"schema_version":"RungVerificationReceipt/v1","schema_version":"RungVerificationReceipt/v1"}',
            "bad_digest": canonical_json({**receipt, "receipt_sha256": "0" * 64}),
            "bad_commit": canonical_json({**receipt, "commit_sha": "A" * 40}),
            "not_json": b"not json",
            "oversized": b" " * (MAX_JSON_BYTES + 1),
        }
        for name, data in malformed.items():
            with self.subTest(name=name):
                receipt_path.write_bytes(data)
                observation = self.base / f"malformed-{name}.json"
                with self.assertRaises(VerificationError):
                    replay_receipt(self.source, receipt_path, observation)
                self.assertFalse(observation.exists())

    def test_dirty_and_untracked_checkouts_are_rejected(self):
        for name, mutate in (
            ("dirty", lambda root: (root / "README.md").write_text("changed\n")),
            ("untracked", lambda root: (root / "new.txt").write_text("new\n")),
            ("ignored", lambda root: (
                (root / ".git" / "info" / "exclude").write_text("ignored.txt\n"),
                (root / "ignored.txt").write_text("ignored\n"),
            )),
        ):
            with self.subTest(name=name):
                clone = self._clone(name)
                mutate(clone)
                output = self.base / f"{name}-receipt.json"
                with self.assertRaisesRegex(VerificationError, "clean"):
                    create_receipt(clone, output)
                self.assertFalse(output.exists())

    def test_index_flags_cannot_hide_worktree_content_drift(self):
        for name, flag in (("skip", "--skip-worktree"), ("assume", "--assume-unchanged")):
            with self.subTest(flag=flag):
                clone = self._clone(name)
                self._git(clone, "update-index", flag, "README.md")
                (clone / "README.md").write_text("concealed change\n", encoding="utf-8")
                self.assertEqual(self._git(clone, "status", "--porcelain"), "")
                output = self.base / f"{name}-receipt.json"
                with self.assertRaisesRegex(VerificationError, "differs from HEAD"):
                    create_receipt(clone, output)
                self.assertFalse(output.exists())

    def test_mid_audit_mutation_reads_immutable_head_bytes(self):
        baseline_path, baseline = self._receipt(name="baseline.json")
        baseline_path.unlink()
        original_run_audit = run_audit
        observed_root = None

        def mutate_while_auditing(root, **kwargs):
            nonlocal observed_root
            observed_root = Path(root)
            original = (self.source / "README.md").read_bytes()
            (self.source / "README.md").write_bytes(b"transient mutation\n")
            try:
                return original_run_audit(root, **kwargs)
            finally:
                (self.source / "README.md").write_bytes(original)

        with mock.patch.object(verification, "run_audit", side_effect=mutate_while_auditing):
            receipt = create_receipt(self.source, self.base / "mutated-receipt.json")
        self.assertNotEqual(observed_root, self.source)
        self.assertEqual(receipt, baseline)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_tracked_symlinks_are_rejected(self):
        clone = self._clone("escaping")
        os.symlink(self.base / "outside", clone / "escape")
        self._git(clone, "add", "escape")
        self._git(clone, "commit", "-q", "-m", "escaping link")
        with self.assertRaisesRegex(VerificationError, "tracked symlinks"):
            create_receipt(clone, self.base / "escape-receipt.json")

        internal = self._clone("internal-link")
        os.symlink("README.md", internal / "readme-link")
        self._git(internal, "add", "readme-link")
        self._git(internal, "commit", "-q", "-m", "internal link")
        with self.assertRaisesRegex(VerificationError, "tracked symlinks"):
            create_receipt(internal, self.base / "internal-link-receipt.json")

    def test_submodules_are_rejected(self):
        clone = self._clone("submodule-parent")
        child = self.base / "submodule-child"
        self._make_repository(child, "Example/Child")
        self._git(clone, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(child), "vendor/child")
        self._git(clone, "commit", "-q", "-m", "submodule")
        with self.assertRaisesRegex(VerificationError, "submodules"):
            create_receipt(clone, self.base / "submodule-receipt.json")

    def test_output_destination_guards(self):
        inside = self.source / "receipt.json"
        with self.assertRaisesRegex(VerificationError, "outside"):
            create_receipt(self.source, inside)

        existing = self.base / "existing.json"
        existing.write_text("existing")
        with self.assertRaisesRegex(VerificationError, "already exists"):
            create_receipt(self.source, existing)

        target = self.base / "target.json"
        target.write_text("target")
        symlink = self.base / "symlink.json"
        symlink.symlink_to(target)
        with self.assertRaisesRegex(VerificationError, "already exists"):
            create_receipt(self.source, symlink)

        real_parent = self.base / "real-parent"
        real_parent.mkdir()
        linked_parent = self.base / "linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        with self.assertRaisesRegex(VerificationError, "unsafe output parent"):
            create_receipt(self.source, linked_parent / "receipt.json")

    def test_output_parent_replacement_fails_closed(self):
        parent = self.base / "swap-parent"
        parent.mkdir()
        moved = self.base / "original-parent"
        original_validate = verification._validate_output

        def replace_after_validation(path, root):
            validated = original_validate(path, root)
            parent.rename(moved)
            parent.mkdir()
            return validated

        with mock.patch.object(verification, "_validate_output", side_effect=replace_after_validation):
            with self.assertRaisesRegex(VerificationError, "parent changed"):
                create_receipt(self.source, parent / "receipt.json")
        self.assertFalse((parent / "receipt.json").exists())
        self.assertFalse((moved / "receipt.json").exists())

    def test_missing_and_unsupported_origins_fail_closed(self):
        self._git(self.source, "remote", "remove", "origin")
        with self.assertRaises(VerificationError):
            create_receipt(self.source, self.base / "missing-origin.json")
        for remote in ("https://gitlab.com/example/project.git", "../local", "git@github.com:owner/repo/extra.git"):
            with self.subTest(remote=remote), self.assertRaises(VerificationError):
                normalize_repository(remote)

    def test_checkout_identity_derives_from_one_captured_commit(self):
        calls = []
        from rung import verification
        original = verification._git

        def recording_git(root, *args, **kwargs):
            calls.append(args)
            return original(root, *args, **kwargs)

        with patch("rung.verification._git", side_effect=recording_git):
            identity = inspect_checkout(self.source)
        self.assertEqual(sum(call == ("rev-parse", "--verify", "HEAD") for call in calls), 1)
        self.assertFalse(any(call[0] in {"show", "cat-file"} for call in calls))
        self.assertFalse(any(call[:2] == ("rev-parse", "--verify") and call[-1] != "HEAD" for call in calls))

    def test_commit_metadata_requires_authenticated_object_bytes(self):
        forged = b"tree " + b"a" * 40 + b"\ncommitter Test <test@example.invalid> 1 +0000\n\nmessage\n"
        with patch("rung.git_snapshot.run_git", return_value=forged):
            with self.assertRaisesRegex(SnapshotError, "commit object digest mismatch"):
                load_commit(self.source, "b" * 40)

    def test_cli_exit_codes_distinguish_mismatch_and_malformed(self):
        receipt_path, receipt = self._receipt()
        changed = dict(receipt)
        changed["tree_sha"] = "a" * 40
        self._rewrite(receipt_path, changed)
        mismatch = subprocess.run(
            [sys.executable, "-m", "rung", "replay", "--root", str(self.source),
             "--receipt", str(receipt_path), "--observation", str(self.base / "mismatch.json")],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(mismatch.returncode, 2)

        receipt_path.write_text("{}", encoding="utf-8")
        malformed_output = self.base / "malformed-observation.json"
        malformed = subprocess.run(
            [sys.executable, "-m", "rung", "replay", "--root", str(self.source),
             "--receipt", str(receipt_path), "--observation", str(malformed_output)],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(malformed.returncode, 1)
        self.assertFalse(malformed_output.exists())

    def test_generated_standalone_verifies_and_replays(self):
        clone = self._clone("standalone-clone")
        receipt = self.base / "standalone-receipt.json"
        observation = self.base / "standalone-observation.json"
        verified = subprocess.run(
            [sys.executable, str(ARTIFACT), "verify", "--root", str(self.source),
             "--receipt", str(receipt)],
            cwd=self.base, text=True, capture_output=True, check=False,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        replayed = subprocess.run(
            [sys.executable, str(ARTIFACT), "replay", "--root", str(clone),
             "--receipt", str(receipt), "--observation", str(observation)],
            cwd=self.base, text=True, capture_output=True, check=False,
        )
        self.assertEqual(replayed.returncode, 0, replayed.stderr)
        self.assertTrue(json.loads(observation.read_text(encoding="utf-8"))["matched"])

    def test_modular_and_standalone_cross_replay(self):
        clone = self._clone("cross-clone")
        modular_receipt = self.base / "modular-receipt.json"
        create_receipt(self.source, modular_receipt)
        standalone_observation = self.base / "standalone-cross-observation.json"
        standalone = subprocess.run(
            [sys.executable, str(ARTIFACT), "replay", "--root", str(clone),
             "--receipt", str(modular_receipt), "--observation", str(standalone_observation)],
            cwd=self.base, text=True, capture_output=True, check=False,
        )
        self.assertEqual(standalone.returncode, 0, standalone.stderr)

        standalone_receipt = self.base / "standalone-cross-receipt.json"
        standalone = subprocess.run(
            [sys.executable, str(ARTIFACT), "verify", "--root", str(clone),
             "--receipt", str(standalone_receipt)],
            cwd=self.base, text=True, capture_output=True, check=False,
        )
        self.assertEqual(standalone.returncode, 0, standalone.stderr)
        observation, matched = replay_receipt(
            self.source, standalone_receipt, self.base / "modular-cross-observation.json"
        )
        self.assertTrue(matched, observation["mismatch_categories"])

    def test_standalone_digest_uses_executed_source_payload(self):
        original = ARTIFACT.read_text(encoding="utf-8")
        marker = "Reproducible verification receipts and replay observations."
        self.assertIn(marker, original)
        tampered = original.replace(marker, "Altered verification source payload.", 1)
        copied = self.base / "tampered-rung-cli.py"
        copied.write_text(tampered, encoding="utf-8")
        baseline = create_receipt(self.source, self.base / "engine-baseline.json")
        output = self.base / "tampered-engine.json"
        result = subprocess.run(
            [sys.executable, str(copied), "verify", "--root", str(self.source),
             "--receipt", str(output)],
            cwd=self.base, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        changed = json.loads(output.read_text(encoding="utf-8"))
        self.assertNotEqual(changed["engine_artifact_sha256"], baseline["engine_artifact_sha256"])


if __name__ == "__main__":
    unittest.main()
