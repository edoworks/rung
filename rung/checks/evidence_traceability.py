"""Check 5: Evidence and traceability for completed work.

Does not give credit merely because .github/workflows exists. CI
workflow existence alone is detected, not enforced or verified.
"""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import find_file, has_ci_workflows, ci_workflow_runs_tests


def check_evidence_traceability(root: Path) -> CheckResult:
    r = CheckResult(
        name="Evidence & traceability",
        description="Evidence index, traceability matrix, or CI artifacts linking work to verified outcomes",
        weight=10, blocking=False,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        source_mappings=[
            {"id": "ibm_adlc", "classification": SOURCES["ibm_adlc"]["classification"].value},
            {"id": "slsa", "classification": SOURCES["slsa"]["classification"].value},
        ],
    )
    candidates = [
        root / "factory" / "evidence" / "index.json",
        root / "docs" / "traceability-matrix.md",
        root / "templates" / "traceability-matrix.md",
        root / "evidence",
        root / ".evidence",
        root / "test-results",
        root / ".test-results",
        root / "CHANGELOG.md",
        root / "docs" / "CHANGELOG.md",
    ]
    found = find_file(root, candidates)
    found = [p for p in found if p.is_dir() or (
        len((text := p.read_text(encoding="utf-8", errors="ignore")).splitlines()) >= 3
        and ("changelog" in text.lower() or "trace" in text.lower() or "evidence" in text.lower())
    )]
    ci_exists = has_ci_workflows(root)
    ci_runs_tests = ci_workflow_runs_tests(root)

    if ci_exists:
        if ci_runs_tests:
            r.evidence.append("CI workflows found that run tests")
        else:
            r.evidence.append("CI workflow files found but do not appear to run tests")
            r.limitations.append("Workflow existence alone does not provide traceability; the workflow must produce test evidence")

    if found:
        r.state = EvidenceState.DETECTED
        if not any("CI workflows" in d for d in r.evidence):
            r.evidence.append(f"Evidence system: {found[0].relative_to(root)}")
    else:
        r.remediation = [
            "Create an evidence trail linking completed work to verification.",
            "Options: a CHANGELOG.md, a factory/evidence/ index, CI workflow",
            "artifacts, or a traceability matrix.",
        ]
    return r
