"""Report renderer — projects AuditResult v1 into preview and PDF formats.

Both the free preview and the paid PDF render from the same immutable
AuditResult. The preview is a JSON subset; the PDF is an HTML document
that can be printed to PDF by a headless browser or weasyprint.

The renderer is deterministic: given the same AuditResult, it produces
the same output. No timestamps are added beyond what's in the result.
"""

from __future__ import annotations

import json
from typing import Optional
from html import escape

from rung.models import AuditResult, CheckResult, EvidenceState, AuthorityLevel
from rung.audit import result_to_dict


def render_preview(result: AuditResult) -> dict:
    """Render the free preview from AuditResult v1.

    Returns only: canonical repository name, exact commit SHA,
    provisional score, authority recommendation, top two findings,
    one recommended action, locked finding count, and opaque audit ticket.
    The ticket is a placeholder — the service layer fills it in.
    """
    checks_sorted = sorted(result.checks, key=lambda c: (not c.blocking, c.name))
    top_two = []
    for c in checks_sorted:
        if not c.passed:
            top_two.append({
                "name": c.name,
                "state": c.state.value if hasattr(c.state, "value") else str(c.state),
                "description": c.description,
            })
        if len(top_two) >= 2:
            break

    one_remediation = ""
    for c in checks_sorted:
        if not c.passed and c.remediation:
            one_remediation = c.remediation[0]
            break

    locked_count = sum(1 for c in result.checks if not c.passed) - len(top_two)

    return {
        "repository": result.repository,
        "commit_sha": result.commit_sha,
        "score": result.score,
        "grade": result.grade,
        "grade_label": result.grade_label,
        "quality_gate": result.quality_gate,
        "authority": result.authority.value if hasattr(result.authority, "value") else str(result.authority),
        "top_two_findings": top_two,
        "recommended_action": one_remediation,
        "locked_finding_count": max(locked_count, 0),
        "audit_ticket": None,
    }


def render_html(result: AuditResult) -> str:
    """Render the full HTML report from AuditResult v1.

    This HTML can be printed to PDF by a headless browser or weasyprint.
    The output is deterministic for the same AuditResult.
    """
    r = result
    authority_val = r.authority.value if hasattr(r.authority, "value") else str(r.authority)

    sections = []

    # Cover
    sections.append(f"""<section class="cover">
  <h1>Rung Public-Evidence Audit Report</h1>
  <p class="repo">{escape(r.repository)}</p>
  {f'<p class="commit">Commit: <code>{escape(r.commit_sha)}</code></p>' if r.commit_sha else ''}
  <p class="meta">Rung {escape(r.rung_version)} · Schema {escape(r.schema_version)} · {escape(r.timestamp)}</p>
</section>""")

    # Executive verdict
    sections.append(f"""<section class="verdict">
  <h2>Executive Verdict</h2>
  <table class="verdict-table">
    <tr><th>Score</th><td>{r.score}/100</td></tr>
    <tr><th>Grade</th><td>{escape(r.grade)} — {escape(r.grade_label)}</td></tr>
    <tr><th>Quality Gate</th><td class="{'pass' if r.quality_gate == 'PASS' else 'fail'}">{r.quality_gate}</td></tr>
    <tr><th>Recommended Authority</th><td>{escape(authority_val.replace("_", " ").title())}</td></tr>
  </table>
</section>""")

    # Public-evidence matrix
    rows = []
    for c in r.checks:
        state_val = c.state.value if hasattr(c.state, "value") else str(c.state)
        conf_val = c.confidence.value if hasattr(c.confidence, "value") else str(c.confidence)
        state_class = state_val
        weight_str = f"{c.weight} pts" if c.weight > 0 else "non-scoring"
        blocking_str = "blocking" if c.blocking else ""
        evidence_html = "<br>".join(f"&rarr; {escape(e)}" for e in c.evidence) if c.evidence else "<em>none</em>"
        limitations_html = "<br>".join(f"&#9888; {escape(l)}" for l in c.limitations) if c.limitations else ""
        remediation_html = "<br>".join(f"{escape(s)}" for s in c.remediation) if c.remediation else ""
        sources_html = ", ".join(escape(sm["id"]) for sm in c.source_mappings) if c.source_mappings else ""

        rows.append(f"""<tr class="{state_class}">
  <td class="state">{escape(state_val.upper())}</td>
  <td>{escape(c.name)} <span class="weight">({weight_str})</span> {f'<span class="blocking">{blocking_str}</span>' if blocking_str else ''}</td>
  <td>{escape(conf_val)}</td>
  <td>{evidence_html}</td>
  <td>{limitations_html}</td>
  <td>{remediation_html}</td>
  <td>{sources_html}</td>
</tr>""")

    sections.append(f"""<section class="matrix">
  <h2>Public-Evidence Matrix</h2>
  <table class="matrix-table">
    <thead>
      <tr><th>State</th><th>Check</th><th>Confidence</th><th>Evidence</th><th>Limitations</th><th>Remediation</th><th>Sources</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</section>""")

    # Critical and high-priority findings
    failed_blocking = [c for c in r.checks if c.blocking and not c.passed]
    if failed_blocking:
        findings_items = []
        for c in failed_blocking:
            state_val = c.state.value if hasattr(c.state, "value") else str(c.state)
            findings_items.append(f"""<li><strong>{escape(c.name)}</strong> [{escape(state_val)}]: {escape(c.description)}<br>
        {'<br>'.join(escape(s) for s in c.remediation)}</li>""")
        sections.append(f"""<section class="findings">
  <h2>Critical and High-Priority Findings</h2>
  <ul class="findings-list">
    {''.join(findings_items)}
  </ul>
</section>""")

    # Full remediation sequence
    all_remediation = [(c.name, c.remediation) for c in r.checks if not c.passed and c.remediation]
    if all_remediation:
        remediation_steps = []
        step_num = 1
        for name, steps in all_remediation:
            for step in steps:
                remediation_steps.append(f"<li>{escape(step)} <em>({escape(name)})</em></li>")
                step_num += 1
        sections.append(f"""<section class="remediation">
  <h2>Full Remediation Sequence</h2>
  <ol class="remediation-list">
    {''.join(remediation_steps)}
  </ol>
</section>""")

    # Source mapping
    all_sources = set()
    for c in r.checks:
        for sm in c.source_mappings:
            all_sources.add(sm["id"])
    if all_sources:
        from rung.sources import SOURCES
        source_lines = []
        for sid in sorted(all_sources):
            if sid in SOURCES:
                s = SOURCES[sid]
                source_lines.append(f"<li><strong>{escape(sid)}</strong>: {escape(s['name'])} — <a href=\"{escape(s['url'])}\">{escape(s['url'])}</a></li>")
        sections.append(f"""<section class="sources">
  <h2>Source Mapping</h2>
  <ul class="source-list">
    {''.join(source_lines)}
  </ul>
</section>""")

    # Limitations and unobservable controls
    unobservable = [c for c in r.checks if hasattr(c.state, "value") and c.state.value == "unobservable"]
    all_limitations = []
    for c in r.checks:
        for lim in c.limitations:
            all_limitations.append(f"<li>{escape(lim)} <em>({escape(c.name)})</em></li>")
    if unobservable:
        for c in unobservable:
            all_limitations.append(f"<li>{escape(c.name)}: control is not observable from public evidence</li>")
    if all_limitations:
        sections.append(f"""<section class="limitations">
  <h2>Limitations and Unobservable Controls</h2>
  <ul class="limitations-list">
    {''.join(all_limitations)}
  </ul>
</section>""")

    # Methodology and report digest
    sections.append(f"""<section class="methodology">
  <h2>Methodology and Report Digest</h2>
  <p>This report is an automated public-evidence assessment. It is informed by
  standards and industry practices (NIST AI RMF, SLSA, OpenSSF Scorecard). It is
  not certification, compliance, or legal advice.</p>
  <p>A public, accountless scan cannot inspect some important enforcement settings.
  GitHub's branch-protection API requires Administration read permission, even for
  reads on public repositories. Rung labels these controls as <strong>unobservable</strong>
  rather than passing or failing them.</p>
  <table class="digest-table">
    <tr><th>Repository</th><td><code>{escape(r.repository)}</code></td></tr>
    {f'<tr><th>Commit SHA</th><td><code>{escape(r.commit_sha)}</code></td></tr>' if r.commit_sha else ''}
    <tr><th>Rung version</th><td>{escape(r.rung_version)}</td></tr>
    <tr><th>Schema version</th><td>{escape(r.schema_version)}</td></tr>
    <tr><th>Timestamp</th><td>{escape(r.timestamp)}</td></tr>
    <tr><th>Report-data SHA-256</th><td><code>{escape(r.report_data_sha256 or "")}</code></td></tr>
  </table>
</section>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rung Public-Evidence Audit Report — {escape(r.repository)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.55; color: #1f2937; max-width: 900px; margin: 0 auto; padding: 40px; }}
    h1 {{ font-size: 1.8rem; border-bottom: 2px solid #7c3aed; padding-bottom: 8px; }}
    h2 {{ font-size: 1.3rem; margin-top: 32px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.9rem; }}
    th {{ text-align: left; padding: 6px 8px; background: #f9fafb; border: 1px solid #e5e7eb; }}
    td {{ padding: 6px 8px; border: 1px solid #e5e7eb; vertical-align: top; }}
    .cover h1 {{ border: none; }}
    .repo {{ font-size: 1.1rem; color: #6b7280; }}
    .commit {{ font-size: 0.85rem; color: #6b7280; }}
    .meta {{ font-size: 0.8rem; color: #9ca3af; }}
    .verdict-table th {{ width: 200px; }}
    .pass {{ color: #059669; font-weight: bold; }}
    .fail {{ color: #dc2626; font-weight: bold; }}
    .matrix-table td {{ font-size: 0.82rem; }}
    .state {{ font-weight: bold; white-space: nowrap; }}
    .detected {{ color: #059669; }}
    .claimed {{ color: #d97706; }}
    .absent {{ color: #dc2626; }}
    .unobservable {{ color: #6366f1; }}
    .verified {{ color: #059669; }}
    .enforced {{ color: #059669; }}
    .weight {{ font-size: 0.78rem; color: #9ca3af; }}
    .blocking {{ font-size: 0.7rem; background: #fee2e2; color: #991b1b; padding: 1px 4px; border-radius: 3px; }}
    .findings-list li, .remediation-list li, .limitations-list li {{ margin-bottom: 8px; }}
    .source-list li {{ font-size: 0.85rem; }}
    .digest-table th {{ width: 180px; }}
    code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 3px; font-size: 0.85em; }}
    a {{ color: #7c3aed; }}
    @media print {{ body {{ max-width: none; padding: 0; }} }}
  </style>
</head>
<body>
  {''.join(sections)}
</body>
</html>"""
    return html


def render_pdf_data(result: AuditResult) -> bytes:
    """Render PDF bytes from AuditResult v1.

    Uses the HTML renderer and converts to PDF. The conversion method
    depends on what's available: weasyprint if installed, otherwise
    raises NotImplementedError with guidance.

    In the private report service, this will be called with a headless
    browser or weasyprint. The factory's production path must be
    deterministic and invoke no LLM.
    """
    html = render_html(result)
    try:
        from weasyprint import HTML as WeasyprintHTML
        pdf_bytes = WeasyprintHTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        raise NotImplementedError(
            "weasyprint is not installed. Install it with: pip install weasyprint\n"
            "Alternatively, use render_html() and print to PDF via a headless browser."
        )