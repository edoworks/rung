"""Check 6: Session ledger / status tracking."""
import json
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import find_file, has_valid_json


def check_session_ledger(root: Path) -> CheckResult:
    r = CheckResult(
        name="Session ledger",
        description="Machine-readable status file, work queue, or changelog for tracking agent sessions",
        weight=5, blocking=False,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        source_mappings=[
            {"id": "anthropic_multiagent", "classification": SOURCES["anthropic_multiagent"]["classification"].value},
            {"id": "ibm_adlc", "classification": SOURCES["ibm_adlc"]["classification"].value},
        ],
    )
    candidates = [
        root / "factory" / "status.json",
        root / "factory" / "queue.json",
        root / "docs" / "sessions" / "current.md",
        root / "sessions" / "current.md",
        root / "SESSIONS.md",
        root / ".factory" / "sessions" / "current.md",
        root / "STATUS.md",
        root / "docs" / "STATUS.md",
        root / "CHANGELOG.md",
    ]
    found = find_file(root, candidates)
    found = [p for p in found if p.suffix != ".json" or (
        has_valid_json(p)
        and any(key in json.loads(p.read_text(encoding="utf-8")) for key in ("state", "status", "active_increment", "items"))
    )]
    if found:
        r.state = EvidenceState.DETECTED
        r.evidence.append(f"Session/status tracking: {found[0].relative_to(root)}")
    else:
        r.remediation = [
            "Create a session ledger or status file (e.g., docs/sessions/current.md,",
            "factory/status.json, or CHANGELOG.md) that records the active work",
            "item, last update timestamp, and any blockers.",
        ]
    return r
