"""Check 10: Independent review requirement."""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import read_text, has_affirmative_pattern


def check_independent_review(root: Path) -> CheckResult:
    r = CheckResult(
        name="Independent review",
        description="Documented requirement for independent review before commit",
        weight=5, blocking=False,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        source_mappings=[
            {"id": "anthropic_multiagent", "classification": SOURCES["anthropic_multiagent"]["classification"].value},
            {"id": "nist_rmf", "classification": SOURCES["nist_rmf"]["classification"].value},
        ],
    )
    patterns = [
        r'(?:independent|rubberduck|peer|code)\s+review',
        r'review\s+(?:before|prior\s+to)\s+(?:commit|merge|push)',
        r'self-review.*review',
    ]
    files_to_check = [root / "AGENTS.md", root / "CONTRIBUTING.md", root / ".github" / "pull_request_template.md", root / "REVIEW.md"]
    found = False
    for f in files_to_check:
        if f.exists():
            content = read_text(f)
            if content is None:
                continue
            if has_affirmative_pattern(content, patterns):
                found = True
                r.evidence.append(f"Review requirement in {f.relative_to(root)}")
    if found:
        r.state = EvidenceState.DETECTED
    else:
        r.remediation = [
            "Add an independent review requirement to AGENTS.md:",
            "  'Before committing: complete self-review, then independent",
            "  (rubberduck) review, then rerun verification, then commit.'",
        ]
    return r
