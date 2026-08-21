"""Check 8: Agent attribution on commits/PRs."""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import read_text, has_affirmative_pattern


def check_agent_attribution(root: Path) -> CheckResult:
    r = CheckResult(
        name="Agent attribution",
        description="Convention for attributing AI-assisted commits and PRs (Generated-by / Co-authored-by)",
        weight=5, blocking=False,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        source_mappings=[
            {"id": "apache_airflow", "classification": SOURCES["apache_airflow"]["classification"].value},
        ],
    )
    patterns = [r'Generated-by:', r'Co-authored-by:', r'Drafted-by:', r'AI-assisted', r'agent-assisted']
    files_to_check = [root / "AGENTS.md", root / ".github" / "pull_request_template.md", root / "CONTRIBUTING.md"]
    found = False
    for f in files_to_check:
        if f.exists():
            content = read_text(f)
            if content is None:
                continue
            if has_affirmative_pattern(content, patterns):
                found = True
                r.evidence.append(f"Attribution convention in {f.relative_to(root)}")
    if found:
        r.state = EvidenceState.DETECTED
    else:
        r.remediation = [
            "Add an attribution convention to AGENTS.md or PR template:",
            "  Generated-by: <Agent Name and Version>",
        ]
    return r
