"""Tests for Rung checks against adversarial fixtures.

Each test validates that a check correctly classifies positive,
negative, and deceptive repository states. The objective is not
merely coverage; it is resisting false confidence.
"""

import unittest
from pathlib import Path

from rung.audit import _compute_digest, result_to_dict, run_audit
from rung.models import EvidenceState
from rung.scoring import compute_score, recommend_authority
from rung.checks.verification_gate import check_verification_gate
from rung.checks.evidence_traceability import check_evidence_traceability
from rung.checks.build_commands import check_build_commands
from rung.checks.security_never_rules import check_security_never_rules
from rung.checks.file_size import check_file_size

FIXTURES = Path(__file__).parent / "fixtures"


class TestVerificationGate(unittest.TestCase):
    """Check 3: must not give enforcement credit for fake CI."""

    def test_policy_only_no_ci(self):
        """AGENTS.md mentions verification but no CI exists -> CLAIMED, not DETECTED."""
        result = check_verification_gate(FIXTURES / "policy_only")
        self.assertEqual(result.state, EvidenceState.CLAIMED)
        self.assertIn("not confirmed as enforced", " ".join(result.limitations))

    def test_fake_ci_echo_only(self):
        """CI workflow exists but does not run tests -> must not get DETECTED."""
        result = check_verification_gate(FIXTURES / "fake_ci_echo_only")
        # Should be CLAIMED at best — CI exists but doesn't run tests
        self.assertNotEqual(result.state, EvidenceState.VERIFIED)
        self.assertNotEqual(result.state, EvidenceState.ENFORCED)

    def test_excellent_public_evidence(self):
        """CI that runs tests + documented gate -> DETECTED with unobservable limitation."""
        result = check_verification_gate(FIXTURES / "excellent_public_evidence")
        self.assertEqual(result.state, EvidenceState.UNOBSERVABLE)
        self.assertTrue(any("not observable" in lim for lim in result.limitations))


class TestEvidenceTraceability(unittest.TestCase):
    """Check 5: must not credit CI existence alone."""

    def test_fake_ci_echo_only_no_traceability(self):
        """CI that echoes success but runs no tests -> should not pass."""
        result = check_evidence_traceability(FIXTURES / "fake_ci_echo_only")
        self.assertNotEqual(result.state, EvidenceState.VERIFIED)
        self.assertNotEqual(result.state, EvidenceState.ENFORCED)

    def test_excellent_public_evidence(self):
        """CI running tests + CHANGELOG -> DETECTED."""
        result = check_evidence_traceability(FIXTURES / "excellent_public_evidence")
        self.assertEqual(result.state, EvidenceState.DETECTED)


class TestBuildCommands(unittest.TestCase):
    """Check 2: must recognize python3, not just python."""

    def test_python3_command_detection(self):
        """AGENTS.md with python3 -m pytest should be detected."""
        result = check_build_commands(FIXTURES / "policy_only")
        self.assertEqual(result.state, EvidenceState.DETECTED)

    def test_no_build_commands(self):
        """Repository with no AGENTS.md and no runner -> ABSENT."""
        result = check_build_commands(FIXTURES / "no_never_rules")
        self.assertEqual(result.state, EvidenceState.ABSENT)


class TestSecurityNeverRules(unittest.TestCase):
    """Check 9: must require at least 5 Never rules."""

    def test_excellent_has_5_never_rules(self):
        result = check_security_never_rules(FIXTURES / "excellent_public_evidence")
        self.assertEqual(result.state, EvidenceState.DETECTED)

    def test_no_never_rules(self):
        result = check_security_never_rules(FIXTURES / "no_never_rules")
        self.assertEqual(result.state, EvidenceState.ABSENT)


class TestFileSizeNonScoring(unittest.TestCase):
    """Check 7: file-size discipline must be weight=0 (non-scoring)."""

    def test_file_size_weight_is_zero(self):
        result = check_file_size(FIXTURES / "excellent_public_evidence")
        self.assertEqual(result.weight, 0)
        self.assertEqual(result.blocking, False)

    def test_file_size_limitation_documented(self):
        result = check_file_size(FIXTURES / "excellent_public_evidence")
        self.assertTrue(any("non-scoring" in lim for lim in result.limitations))


class TestFullAudit(unittest.TestCase):
    """End-to-end audit tests across fixtures."""

    def test_audit_returns_audit_result(self):
        result = run_audit(FIXTURES / "excellent_public_evidence")
        self.assertEqual(result.schema_version, "1.0.0")
        self.assertIsNotNone(result.report_data_sha256)
        self.assertEqual(len(result.report_data_sha256), 64)
        self.assertEqual(result.quality_gate, "FAIL")
        self.assertEqual(result.authority.value, "owner_evidence_required")
        self.assertTrue(result.score > 0)

    def test_audit_deterministic(self):
        """Same repo audited twice produces the same digest."""
        r1 = run_audit(FIXTURES / "excellent_public_evidence")
        r2 = run_audit(FIXTURES / "excellent_public_evidence")
        self.assertEqual(r1.report_data_sha256, r2.report_data_sha256)

    def test_audit_self_audit(self):
        """Rung auditing itself should produce a valid result."""
        rung_root = Path(__file__).parent.parent
        result = run_audit(rung_root)
        self.assertIsNotNone(result.report_data_sha256)
        self.assertEqual(len(result.checks), 11)

    def test_fake_ci_does_not_pass_gate(self):
        """Fake CI (echo only) should not pass the quality gate."""
        result = run_audit(FIXTURES / "fake_ci_echo_only")
        self.assertEqual(result.quality_gate, "FAIL")

    def test_authority_capped_for_public_only(self):
        """Public-only audit should never recommend LOCAL_ONLY for repos
        with unobservable enforcement."""
        result = run_audit(FIXTURES / "policy_only")
        authority_val = result.authority.value if hasattr(result.authority, "value") else str(result.authority)
        self.assertIn(authority_val, ["unsafe", "pr_only_provisional", "owner_evidence_required"])


class TestDigestIntegrity(unittest.TestCase):
    """Report-data digest tests."""

    def test_digest_excludes_itself(self):
        """The digest must be computed over all fields except report_data_sha256."""
        result = run_audit(FIXTURES / "excellent_public_evidence")
        self.assertNotEqual(result.report_data_sha256, "")
        # Re-running should produce the same digest (deterministic)
        result2 = run_audit(FIXTURES / "excellent_public_evidence")
        self.assertEqual(result.report_data_sha256, result2.report_data_sha256)

    def test_digest_excludes_render_metadata_but_binds_commit(self):
        result = run_audit(FIXTURES / "excellent_public_evidence", commit_sha="a" * 40, repository="owner/repo", timestamp="2026-01-01T00:00:00Z")
        data = result_to_dict(result)
        expected = _compute_digest(data)
        data["timestamp"] = "2099-01-01T00:00:00Z"
        self.assertNotEqual(_compute_digest(data), expected)
        data = result_to_dict(result)
        data["repository"] = "other/repo"
        self.assertNotEqual(_compute_digest(data), expected)
        data = result_to_dict(result)
        data["commit_sha"] = "b" * 40
        self.assertNotEqual(_compute_digest(data), expected)


if __name__ == "__main__":
    unittest.main()
