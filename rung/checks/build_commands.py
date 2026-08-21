"""Check 2: Build/test commands declared and runnable."""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import read_text, detect_build_commands


def check_build_commands(root: Path) -> CheckResult:
    r = CheckResult(
        name="Build & test commands",
        description="AGENTS.md declares concrete build/test commands that exist and run",
        weight=15, blocking=True,
        state=EvidenceState.ABSENT,
        confidence=Confidence.HIGH,
        blocking_for=["local", "pr", "merge"],
        source_mappings=[
            {"id": "openai_codex", "classification": SOURCES["openai_codex"]["classification"].value},
            {"id": "github_copilot", "classification": SOURCES["github_copilot"]["classification"].value},
        ],
    )
    agents_md = root / "AGENTS.md"
    if not agents_md.exists():
        r.remediation = ["First create an AGENTS.md (see Check 1), then declare build/test commands in it."]
        return r

    content = read_text(agents_md) or ""
    found_cmds = detect_build_commands(content)

    makefile = root / "Makefile"
    justfile = root / "justfile"
    package_json = root / "package.json"

    has_runner = makefile.exists() or justfile.exists() or package_json.exists()
    if found_cmds:
        r.state = EvidenceState.DETECTED
        r.evidence.append(f"Declared commands: {', '.join(set(found_cmds[:5]))}")
        if has_runner:
            r.evidence.append("Build runner found (Makefile/justfile/package.json)")
    elif has_runner:
        r.state = EvidenceState.CLAIMED
        r.evidence.append("Build runner found but not referenced in AGENTS.md")
        r.limitations.append("AGENTS.md should explicitly name the build/test commands agents must use")
        r.remediation = [
            "Add a 'Build & Test' section to AGENTS.md with the exact commands, e.g.:",
            "  npm test     # run all tests",
            "  npm run build  # build the project",
        ]
    else:
        r.remediation = [
            "Add a Makefile or justfile with 'test' and 'build' targets,",
            "then reference them in AGENTS.md.",
        ]
    return r