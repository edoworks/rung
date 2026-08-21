"""Check 9: Security 'Never' rules in agent policy."""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import read_text, count_pattern


def check_security_never_rules(root: Path) -> CheckResult:
    r = CheckResult(
        name="Security Never-rules",
        description="AGENTS.md or SECURITY.md enumerates hard 'Never' rules for agents",
        weight=10, blocking=True,
        state=EvidenceState.ABSENT,
        confidence=Confidence.HIGH,
        blocking_for=["local", "pr", "merge", "release"],
        source_mappings=[
            {"id": "nist_rmf", "classification": SOURCES["nist_rmf"]["classification"].value},
            {"id": "apache_airflow", "classification": SOURCES["apache_airflow"]["classification"].value},
        ],
    )
    files_to_check = [root / "AGENTS.md", root / "SECURITY.md", root / ".github" / "SECURITY.md"]
    never_count = 0
    for f in files_to_check:
        if f.exists():
            content = read_text(f)
            if content is None:
                continue
            never_count += count_pattern(content, r'\b[Nn]ever\b')
    if never_count >= 5:
        r.state = EvidenceState.DETECTED
        r.evidence.append(f"Found {never_count} 'Never' rules across policy files")
    elif never_count >= 1:
        r.state = EvidenceState.CLAIMED
        r.evidence.append(f"Found {never_count} 'Never' rule(s) — recommend at least 5")
        r.limitations.append("Consider adding more explicit 'Never' rules for security boundaries")
        r.remediation = [
            "Add more 'Never' rules to AGENTS.md or SECURITY.md, e.g.:",
            "  Never commit secrets, API keys, or credentials",
            "  Never expose the Docker socket to construction agents",
            "  Never use destructive git operations without explicit request",
        ]
    else:
        r.remediation = [
            "Add a 'Never' rules section to AGENTS.md or SECURITY.md.",
        ]
    return r