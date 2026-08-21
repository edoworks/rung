"""Check 11: Cyclic verification loop (plan->build->verify->fix->verify)."""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import read_text, has_affirmative_pattern


def check_cyclic_verification(root: Path) -> CheckResult:
    r = CheckResult(
        name="Cyclic verification",
        description="Workflow loops: plan -> build -> verify -> fix -> verify until pass",
        weight=5, blocking=False,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        source_mappings=[
            {"id": "anthropic_multiagent", "classification": SOURCES["anthropic_multiagent"]["classification"].value},
        ],
    )
    patterns = [
        r'(?:trycycle|try.cycle|verification.loop|fix.loop)',
        r'(?:plan|build|verify|review|fix).*loop',
        r'rerun.*verification',
        r're-?verify',
        r'(?:if.*fail|on.*fail).*fix.*(?:verify|test)',
    ]
    files_to_check = [root / "AGENTS.md", root / "CONTRIBUTING.md"]
    found = False
    for f in files_to_check:
        if f.exists():
            content = read_text(f)
            if content is None:
                continue
            if has_affirmative_pattern(content, patterns):
                found = True
                r.evidence.append(f"Cyclic verification in {f.relative_to(root)}")
    if found:
        r.state = EvidenceState.DETECTED
    else:
        r.remediation = [
            "Document a cyclic verification loop in AGENTS.md:",
            "  plan -> build -> verify -> (if fail) fix -> verify again -> review",
        ]
    return r
