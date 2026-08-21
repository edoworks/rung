"""Check 7: File-size discipline (non-scoring maintainability appendix).

This check has weight=0 and does NOT contribute to the governance score.
It appears in the report as a maintainability appendix. The 500/800 LoC
thresholds come from openai/codex's AGENTS.md engineering convention, not
an autonomous-agent governance standard.
"""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES, SOURCE_EXTENSIONS, IGNORED_PARTS, WATCH_LOC, SMELL_LOC, DEFECT_LOC
from rung.evidence import count_source_loc, is_test_file


def check_file_size(root: Path) -> CheckResult:
    r = CheckResult(
        name="File-size discipline",
        description=f"Source files within size thresholds (warn>{WATCH_LOC} LoC, fail>{SMELL_LOC} LoC) — non-scoring maintainability appendix",
        weight=0, blocking=False,
        state=EvidenceState.VERIFIED,
        confidence=Confidence.HIGH,
        source_mappings=[
            {"id": "openai_codex", "classification": SOURCES["openai_codex"]["classification"].value},
        ],
        limitations=[
            "File-size thresholds come from openai/codex's AGENTS.md engineering convention, not an autonomous-agent governance standard.",
            "This check is non-scoring and appears only in the maintainability appendix.",
        ],
    )
    large_files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix not in SOURCE_EXTENSIONS:
            continue
        if is_test_file(path):
            continue
        loc = count_source_loc(path)
        if loc >= DEFECT_LOC:
            large_files.append(("DEFECT", path.relative_to(root), loc))
        elif loc >= SMELL_LOC:
            large_files.append(("SMELL", path.relative_to(root), loc))
        elif loc >= WATCH_LOC:
            large_files.append(("WATCH", path.relative_to(root), loc))

    if not large_files:
        r.evidence.append("All source files within thresholds")
    else:
        r.state = EvidenceState.ABSENT
        for level, rel, loc in large_files[:10]:
            r.evidence.append(f"[{level}] {rel} ({loc} LoC)")
        r.remediation = [
            f"Target: modules under {WATCH_LOC} LoC (excluding tests)",
            f"Hard cap: files over {SMELL_LOC} LoC must add new functionality",
            "in a new module unless there is a documented reason not to.",
            "Consider splitting large files or adding an exemption comment.",
        ]
    return r