"""Check 1: Agent policy file exists."""
import re
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES, IGNORED_PARTS
from rung.evidence import detect_build_commands, find_file, read_text


HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
PLACEHOLDER = re.compile(r"^(?:todo|tbd|placeholder|coming soon|no instructions)\b", re.IGNORECASE)
SECURITY_INSTRUCTION = re.compile(r"\b(?:never|must not|do not|don't|avoid|require|only|forbid|prohibit|reject)\b", re.IGNORECASE)


def _policy_sections(content: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    lines = content.splitlines()
    fence: tuple[str, int] | None = None
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        fence_line = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence is None and fence_line:
            marker = fence_line.group(1)
            fence = (marker[0], len(marker))
            index += 1
            continue
        if fence is not None and re.fullmatch(rf"{re.escape(fence[0])}{{{fence[1]},}}\s*", stripped):
            fence = None
            index += 1
            continue
        leading_spaces = len(raw_line) - len(raw_line.lstrip(" "))
        heading = None if fence is not None or leading_spaces > 3 else HEADING.match(stripped)
        if fence is None and leading_spaces <= 3 and not heading and index + 1 < len(lines) \
                and len(lines[index + 1]) - len(lines[index + 1].lstrip(" ")) <= 3 \
                and re.fullmatch(r"[=-]{3,}\s*", lines[index + 1].strip()):
            heading = re.match(r"^(.+)$", stripped)
            index += 1
        if heading:
            current = heading.group(1).strip().lower()
            sections.setdefault(current, [])
        elif current is not None:
            line = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", stripped)
            line = re.sub(r"^\[[ xX]\]\s*", "", line).strip()
            if line and not PLACEHOLDER.match(line):
                sections[current].append(line)
        index += 1
    return sections


def _has_substantive_policy(content: str) -> bool:
    sections = _policy_sections(content)
    has_commands = any(detect_build_commands("\n".join(body)) and re.search(r"\b(?:build|test|local commands?)\b", heading)
                       for heading, body in sections.items())
    has_security = any(any(SECURITY_INSTRUCTION.search(line) for line in body)
                       and re.search(r"\b(?:security|never[ -]?rules?)\b", heading)
                       for heading, body in sections.items())
    return has_commands and has_security


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
    candidates_found = find_file(root, candidates)
    found = [p for p in candidates_found if _has_substantive_policy(read_text(p) or "")]
    nested = list(root.rglob("AGENTS.md"))
    nested = [p for p in nested if p != root / "AGENTS.md" and all(part not in IGNORED_PARTS for part in p.relative_to(root).parts[:-1]) and p.is_file()]

    if found:
        r.state = EvidenceState.DETECTED
        r.evidence.append(f"Found: {found[0].relative_to(root)}")
        if len(found) > 1:
            r.evidence.append(f"Also found: {', '.join(str(p.relative_to(root)) for p in found[1:])}")
        if nested:
            r.evidence.append(f"Nested AGENTS.md files: {len(nested)} (good for monorepos)")
    elif candidates_found:
        r.state = EvidenceState.CLAIMED
        r.evidence.append(f"Found policy file without substantive command and security guidance: {candidates_found[0].relative_to(root)}")
        r.limitations.append("Heading-only or placeholder policy files do not provide actionable agent instructions")
        r.remediation = ["Add substantive Local Commands (or Build/Test) and Never-Rules (or Security) sections."]
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
