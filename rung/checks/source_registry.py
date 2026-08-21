"""Check 4: Source-of-truth registry for external claims."""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES


def check_source_registry(root: Path) -> CheckResult:
    r = CheckResult(
        name="Source-of-truth registry",
        description="Machine-readable source registry for external claims and references",
        weight=10, blocking=False,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        source_mappings=[
            {"id": "nist_rmf", "classification": SOURCES["nist_rmf"]["classification"].value},
            {"id": "ibm_adlc", "classification": SOURCES["ibm_adlc"]["classification"].value},
        ],
    )
    candidates = [
        root / "docs" / "research" / "sources.json",
        root / "docs" / "sources.json",
        root / "SOURCES.md",
        root / "docs" / "SOURCES.md",
    ]
    found = [p for p in candidates if p.exists()]
    if found:
        r.state = EvidenceState.DETECTED
        r.evidence.append(f"Source registry: {found[0].relative_to(root)}")
    else:
        r.remediation = [
            "Create a source registry (e.g., docs/research/sources.json) that",
            "records every external source cited in the repo with a SRC-ID,",
            "URL, and classification (first_party / preprint / standard).",
        ]
    return r