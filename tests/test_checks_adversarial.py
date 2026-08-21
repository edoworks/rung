"""Every check rejects a representative deceptive repository state."""

import tempfile
import unittest
from pathlib import Path

from rung.checks import ALL_CHECKS
from rung.models import EvidenceState


FIXTURES = Path(__file__).parent / "fixtures"


class TestEveryCheckAdversarially(unittest.TestCase):
    def test_positive_and_negative_baselines_cover_every_check(self):
        positive = FIXTURES / "excellent_public_evidence"
        with tempfile.TemporaryDirectory() as directory:
            negative = Path(directory)
            for check in ALL_CHECKS:
                with self.subTest(check=check.__name__, state="positive"):
                    self.assertIn(check(positive).state, (EvidenceState.DETECTED, EvidenceState.VERIFIED, EvidenceState.UNOBSERVABLE))
                if check.__name__ != "check_file_size":
                    with self.subTest(check=check.__name__, state="negative"):
                        self.assertEqual(check(negative).state, EvidenceState.ABSENT)

    def test_deceptive_inputs_do_not_receive_detected_credit(self):
        cases = {
            "check_agent_policy": {"AGENTS.md": "build security\nplaceholder\nplaceholder\nplaceholder\nplaceholder\n"},
            "check_build_commands": {"AGENTS.md": "python3 missing.py\n"},
            "check_verification_gate": {
                "AGENTS.md": "Verification is optional.\n",
                ".github/workflows/ci.yml": "steps:\n  - run: |\n      echo pytest\n",
            },
            "check_source_registry": {"docs/research/sources.json": "{\"x\": 1}\n"},
            "check_evidence_traceability": {"CHANGELOG.md": "# Placeholder\nfoo\nbar\n"},
            "check_session_ledger": {"factory/status.json": "{\"x\": 1}\n"},
            "check_file_size": {"latest.py": "x = 1\n" * 900},
            "check_agent_attribution": {"AGENTS.md": "Do not use Generated-by trailers.\n"},
            "check_security_never_rules": {"AGENTS.md": "Never weaken security.\n" * 5},
            "check_independent_review": {"AGENTS.md": "Independent review is optional.\n"},
            "check_cyclic_verification": {"AGENTS.md": "Reverify whenever convenient.\n"},
        }
        checks = {check.__name__: check for check in ALL_CHECKS}
        for name, files in cases.items():
            with self.subTest(check=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for relative, content in files.items():
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                self.assertNotIn(
                    checks[name](root).state,
                    (EvidenceState.DETECTED, EvidenceState.ENFORCED, EvidenceState.VERIFIED),
                    name,
                )


if __name__ == "__main__":
    unittest.main()
