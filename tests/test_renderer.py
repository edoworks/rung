"""Tests for the Rung report renderer.

Validates that the preview and HTML projections render from the same
AuditResult, that rendering is deterministic, and that 5 representative
fixtures produce valid output.
"""

import unittest
from pathlib import Path

from rung.audit import run_audit
from rung.renderer import render_preview, render_html

FIXTURES = Path(__file__).parent / "fixtures"


class TestPreview(unittest.TestCase):
    """Preview projection tests."""

    def test_preview_has_required_fields(self):
        result = run_audit(FIXTURES / "excellent_public_evidence")
        preview = render_preview(result)
        for field in ["repository", "commit_sha", "score", "grade",
                       "quality_gate", "authority", "top_two_findings",
                       "recommended_action", "locked_finding_count",
                       "audit_ticket"]:
            self.assertIn(field, preview, f"preview must have field {field}")

    def test_preview_top_two_findings_max_two(self):
        result = run_audit(FIXTURES / "no_never_rules")
        preview = render_preview(result)
        self.assertLessEqual(len(preview["top_two_findings"]), 2)

    def test_preview_locked_count_non_negative(self):
        result = run_audit(FIXTURES / "no_never_rules")
        preview = render_preview(result)
        self.assertGreaterEqual(preview["locked_finding_count"], 0)

    def test_preview_audit_ticket_is_none(self):
        """The ticket is a placeholder; the service fills it in."""
        result = run_audit(FIXTURES / "excellent_public_evidence")
        preview = render_preview(result)
        self.assertIsNone(preview["audit_ticket"])

    def test_preview_deterministic(self):
        r1 = run_audit(FIXTURES / "excellent_public_evidence")
        r2 = run_audit(FIXTURES / "excellent_public_evidence")
        p1 = render_preview(r1)
        p2 = render_preview(r2)
        self.assertEqual(p1, p2)


class TestHtmlReport(unittest.TestCase):
    """HTML report tests."""

    def test_html_contains_all_sections(self):
        result = run_audit(FIXTURES / "excellent_public_evidence")
        html = render_html(result)
        self.assertIn("Executive Verdict", html)
        self.assertIn("Public-Evidence Matrix", html)
        self.assertIn("Methodology and Report Digest", html)
        self.assertIn("Report-data SHA-256", html)

    def test_html_contains_evidence_states(self):
        result = run_audit(FIXTURES / "excellent_public_evidence")
        html = render_html(result)
        self.assertIn("DETECTED", html)

    def test_html_contains_authority(self):
        result = run_audit(FIXTURES / "policy_only")
        html = render_html(result)
        authority_val = result.authority.value if hasattr(result.authority, "value") else str(result.authority)
        self.assertIn(authority_val.upper(), html.upper())

    def test_html_deterministic(self):
        r1 = run_audit(FIXTURES / "excellent_public_evidence")
        r2 = run_audit(FIXTURES / "excellent_public_evidence")
        h1 = render_html(r1)
        h2 = render_html(r2)
        self.assertEqual(h1, h2)

    def test_html_contains_limitations_section(self):
        result = run_audit(FIXTURES / "excellent_public_evidence")
        html = render_html(result)
        self.assertIn("Limitations", html)


class TestFiveRepresentativeRepositories(unittest.TestCase):
    """Validate that 5 representative fixtures produce valid previews and HTML."""

    FIXTURE_NAMES = [
        "excellent_public_evidence",
        "policy_only",
        "fake_ci_echo_only",
        "no_never_rules",
    ]

    def test_all_fixtures_produce_valid_preview(self):
        for name in self.FIXTURE_NAMES:
            with self.subTest(fixture=name):
                result = run_audit(FIXTURES / name)
                preview = render_preview(result)
                self.assertIn("score", preview)
                self.assertIn("authority", preview)
                self.assertIsInstance(preview["top_two_findings"], list)

    def test_all_fixtures_produce_valid_html(self):
        for name in self.FIXTURE_NAMES:
            with self.subTest(fixture=name):
                result = run_audit(FIXTURES / name)
                html = render_html(result)
                self.assertIn("<!DOCTYPE html>", html)
                self.assertIn("</html>", html)
                self.assertIn("Rung", html)

    def test_self_audit_produces_valid_output(self):
        """Rung-on-Rung: the repo auditing itself produces valid output."""
        rung_root = Path(__file__).parent.parent
        result = run_audit(rung_root)
        preview = render_preview(result)
        html = render_html(result)
        self.assertIn("score", preview)
        self.assertIn("<!DOCTYPE html>", html)


class TestSampleReportGeneration(unittest.TestCase):
    """Generate the Rung-on-Rung sample report."""

    def test_generate_sample_html(self):
        """Generate sample HTML report for Rung auditing itself."""
        rung_root = Path(__file__).parent.parent
        result = run_audit(rung_root)
        html = render_html(result)
        self.assertTrue(len(html) > 1000, "sample HTML report must be substantial")
        self.assertIn("Rung Public-Evidence Audit Report", html)


if __name__ == "__main__":
    unittest.main()