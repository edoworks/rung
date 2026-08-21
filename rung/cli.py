#!/usr/bin/env python3
"""Rung CLI — AI Agent Governance Audit

Scores a repository's readiness for AI coding agent governance using 11
weighted checks derived from published standards and industry best practices.

Outputs a numeric score (0-100), a letter grade (A-E), a quality gate
verdict (PASS/FAIL), evidence states, and actionable next steps for each gap.

Usage:
    python3 -m rung.cli [--root /path/to/your/repo] [--json]

Exit codes:
    0 — quality gate passed (all blocking checks passed)
    1 — quality gate failed (one or more blocking checks failed)

License: MIT
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rung.audit import run_audit, result_to_dict
from rung.scoring import GRADE_LABELS


def format_report(result) -> str:
    """Format a human-readable text report from AuditResult."""
    lines = []
    lines.append("=" * 60)
    lines.append("  Rung — AI Agent Governance Audit")
    lines.append("=" * 60)
    lines.append(f"  Repository: {result.repository}")
    if result.commit_sha:
        lines.append(f"  Commit: {result.commit_sha}")
    lines.append(f"  Score: {result.score}/100  Grade: {result.grade} ({result.grade_label})")
    lines.append(f"  Quality Gate: {result.quality_gate}")
    lines.append(f"  Authority: {result.authority.value if hasattr(result.authority, 'value') else result.authority}")
    lines.append(f"  Rung version: {result.rung_version}  Schema: {result.schema_version}")
    lines.append(f"  Timestamp: {result.timestamp}")
    lines.append(f"  Report digest: {result.report_data_sha256}")
    lines.append("=" * 60)
    lines.append("")

    for c in result.checks:
        status = c.state.value if hasattr(c.state, "value") else str(c.state)
        blocking_tag = " [blocking]" if c.blocking else ""
        weight_tag = f" ({c.weight} pts)" if c.weight > 0 else " (non-scoring)"
        lines.append(f"  [{status.upper()}] {c.name}{weight_tag}{blocking_tag}")
        lines.append(f"         {c.description}")
        for e in c.evidence:
            lines.append(f"         -> {e}")
        for lim in c.limitations:
            lines.append(f"         ! {lim}")
        if c.source_mappings:
            src_ids = [sm["id"] for sm in c.source_mappings]
            lines.append(f"         Sources: {', '.join(src_ids)}")
        if not c.passed and c.remediation:
            lines.append("         Remediation:")
            for step in c.remediation:
                lines.append(f"           {step}")
        lines.append("")

    lines.append("-" * 60)
    lines.append(f"  Score: {result.score}/100  Grade: {result.grade} ({result.grade_label})")
    lines.append(f"  Quality Gate: {result.quality_gate}")
    lines.append(f"  Authority: {result.authority.value if hasattr(result.authority, 'value') else result.authority}")
    failed_blocking = [c for c in result.checks if c.blocking and not c.passed]
    if failed_blocking:
        lines.append(f"  Blocking failures: {len(failed_blocking)}")
        for c in failed_blocking:
            lines.append(f"    - {c.name} [{c.state.value if hasattr(c.state, 'value') else c.state}]")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rung CLI — AI Agent Governance Audit")
    parser.add_argument("--root", default=".", help="Repository root to audit")
    parser.add_argument("--commit-sha", type=lambda value: value if re.fullmatch(r"[0-9a-f]{40}", value) else parser.error("--commit-sha must be 40 lowercase hex characters"), help="Exact audited commit SHA")
    parser.add_argument("--repository", help="Stable repository identifier for the result digest")
    parser.add_argument("--timestamp", help="Explicit RFC 3339 report timestamp for deterministic rendering")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--preview", action="store_true", help="Output free preview JSON")
    parser.add_argument("--html", action="store_true", help="Output full HTML report")
    parser.add_argument("--pdf", action="store_true", help="Output PDF (requires weasyprint)")
    parser.add_argument("-o", "--output", help="Write output to file instead of stdout")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = run_audit(root, commit_sha=args.commit_sha, repository=args.repository, timestamp=args.timestamp)

    if args.preview:
        from rung.renderer import render_preview
        output = json.dumps(render_preview(result), indent=2)
    elif args.html:
        from rung.renderer import render_html
        output = render_html(result)
    elif args.pdf:
        from rung.renderer import render_pdf_data
        pdf_bytes = render_pdf_data(result)
        if args.output:
            Path(args.output).write_bytes(pdf_bytes)
            return 0 if result.quality_gate == "PASS" else 1
        else:
            sys.stdout.buffer.write(pdf_bytes)
            return 0 if result.quality_gate == "PASS" else 1
    elif args.json:
        output = json.dumps(result_to_dict(result), indent=2)
    else:
        output = format_report(result)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)

    return 0 if result.quality_gate == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
