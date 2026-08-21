"""Check 1: Agent policy file exists."""
import re
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES, IGNORED_PARTS
from rung.evidence import find_file, read_text


def check_agent_policy(root: Path) -> CheckResult:
    r = CheckResult(
        name="Agent policy file",
        description="AGENTS.md or .github/copilot-instructions.md exists at repo root",
        weight=15, blocking=True,
        state=EvidenceState.ABSENT,
        confidence=Confidence.HIGH,
        blocking_for=["local", "pr", "merge", "release"],
        source_mappings=[
            {"id": "agents_md", "classification": SOURCES["agents_md"]["classification"].value},
            {"id": "github_copilot", "classification": SOURCES["github_copilot"]["classification"].value},
        ],
    )
    candidates = [
        root / "AGENTS.md",
        root / ".github" / "copilot-instructions.md",
        root / "CLAUDE.md",
        root / "GEMINI.md",
    ]
    found = find_file(root, candidates)
    found = [p for p in found if all(
        re.search(pattern, read_text(p) or "", re.IGNORECASE | re.MULTILINE)
        for pattern in (r"^#{1,6}\s+.*(?:build|test)", r"^#{1,6}\s+.*security")
    )]
    nested = list(root.rglob("AGENTS.md"))
    nested = [p for p in nested if p != root / "AGENTS.md" and all(part not in IGNORED_PARTS for part in p.relative_to(root).parts[:-1]) and p.is_file()]

    if found:
        r.state = EvidenceState.DETECTED
        r.evidence.append(f"Found: {found[0].relative_to(root)}")
        if len(found) > 1:
            r.evidence.append(f"Also found: {', '.join(str(p.relative_to(root)) for p in found[1:])}")
        if nested:
            r.evidence.append(f"Nested AGENTS.md files: {len(nested)} (good for monorepos)")
    else:
        r.remediation = [
            "Create an AGENTS.md at the repo root with these sections:",
            "  1. Project overview (what the project does)",
            "  2. Build/test commands (exact commands agents should run)",
            "  3. Code style conventions",
            "  4. Testing instructions",
            "  5. Security considerations (what agents must never do)",
            f"See exemplars: {SOURCES['openai_codex']['url']}",
        ]
    return r
