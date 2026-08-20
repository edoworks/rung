#!/usr/bin/env python3
"""Rung CLI — AI Agent Governance Audit

Scores a repository's readiness for AI coding agent governance using 11
weighted checks derived from published standards and industry best practices.

Outputs a numeric score (0-100), a letter grade (A-E), a quality gate
verdict (PASS/FAIL), and actionable next steps for each gap found.

Usage:
    python3 rung-cli.py [--root /path/to/your/repo] [--json]

Exit codes:
    0 — quality gate passed (all blocking checks passed)
    1 — quality gate failed (one or more blocking checks failed)

License: MIT
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Cited sources — each check references credible, verifiable sources.
# These are the foundations for the governance principles the CLI tests.
# ---------------------------------------------------------------------------

SOURCES = {
    "agents_md": {
        "name": "agents.md (Linux Foundation / AAIF)",
        "url": "https://agents.md",
        "note": "Cross-vendor agent policy spec, adopted by 60k+ repos. "
                "Defines AGENTS.md as the de-facto agent instruction file.",
    },
    "github_copilot": {
        "name": "GitHub Copilot repository custom instructions",
        "url": "https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot",
        "note": "Official GitHub docs for .github/copilot-instructions.md and "
                "AGENTS.md precedence (nearest file in directory tree wins).",
    },
    "nist_rmf": {
        "name": "NIST AI Risk Management Framework 1.0",
        "url": "https://nist.gov/itl/ai-risk-management-framework",
        "note": "US government framework. Four functions: Govern, Map, "
                "Measure, Manage. Voluntary but widely adopted.",
    },
    "anthropic_multiagent": {
        "name": "Anthropic — How we built our multi-agent research system",
        "url": "https://www.anthropic.com/engineering/multi-agent-research-system",
        "note": "Production guidance on agent evaluation: LLM-as-judge rubrics, "
                "end-state evaluation, durable execution, checkpointing.",
    },
    "openai_codex": {
        "name": "openai/codex AGENTS.md (exemplar)",
        "url": "https://github.com/openai/codex/blob/main/AGENTS.md",
        "note": "322-line root AGENTS.md with 500/800 LoC thresholds, "
                "change-size guidance, mandatory integration tests.",
    },
    "apache_airflow": {
        "name": "apache/airflow AGENTS.md (exemplar)",
        "url": "https://github.com/apache/airflow/blob/main/AGENTS.md",
        "note": "522-line AGENTS.md with Generated-by attribution, "
                "Drafted-by footer, Never-rules, apache-magpie framework.",
    },
    "ibm_adlc": {
        "name": "IBM — Agent Development Lifecycle",
        "url": "https://www.ibm.com/think/topics/agent-development-lifecycle-adlc",
        "note": "Trace layer concept: every AI agent needs an action "
                "accountability trace.",
    },
    "slsa": {
        "name": "SLSA v1.2 (Supply-chain Levels for Software Artifacts)",
        "url": "https://slsa.dev/spec/v1.2/",
        "note": "OpenSSF standard for build provenance. Applies to "
                "agent-produced artifacts.",
    },
    "iso_42001": {
        "name": "ISO/IEC 42001:2023 — AI management system standard",
        "url": "https://www.iso.org/standard/83730.html",
        "note": "Certifiable AI Management System standard. Plan-do-check-act "
                "for AI.",
    },
}

# ---------------------------------------------------------------------------
# Scoring model — 11 checks, weighted to 100 points.
# Blocking checks must pass for the quality gate to pass.
# ---------------------------------------------------------------------------

WATCH_LOC = 500
SMELL_LOC = 800
DEFECT_LOC = 1200

SOURCE_EXTENSIONS = {".py", ".swift", ".gd", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb"}
IGNORED_PARTS = {".git", "build", "dist", "node_modules", "DerivedData", ".venv", "venv", ".build", "Pods", "target", "__pycache__"}


@dataclass
class CheckResult:
    name: str
    description: str
    weight: int
    blocking: bool
    passed: bool
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def check_agent_policy(root: Path) -> CheckResult:
    """Check 1: Agent policy file exists (AGENTS.md or equivalent)."""
    r = CheckResult(
        name="Agent policy file",
        description="AGENTS.md or .github/copilot-instructions.md exists at repo root",
        weight=15, blocking=True, passed=False,
        sources=["agents_md", "github_copilot"],
    )
    candidates = [
        root / "AGENTS.md",
        root / ".github" / "copilot-instructions.md",
        root / "CLAUDE.md",
        root / "GEMINI.md",
    ]
    found = [p for p in candidates if p.exists()]
    nested = list(root.rglob("AGENTS.md"))
    nested = [p for p in nested if p != root / "AGENTS.md" and any(part not in IGNORED_PARTS for part in p.relative_to(root).parts[:-1])]

    if found:
        r.passed = True
        r.details.append(f"Found: {found[0].relative_to(root)}")
        if len(found) > 1:
            r.details.append(f"Also found: {', '.join(str(p.relative_to(root)) for p in found[1:])}")
        if nested:
            r.details.append(f"Nested AGENTS.md files: {len(nested)} (good for monorepos)")
    else:
        r.next_steps = [
            "Create an AGENTS.md at the repo root with these sections:",
            "  1. Project overview (what the project does)",
            "  2. Build/test commands (exact commands agents should run)",
            "  3. Code style conventions",
            "  4. Testing instructions",
            "  5. Security considerations (what agents must never do)",
            "See exemplars:",
            f"  {SOURCES['openai_codex']['url']}",
            f"  {SOURCES['apache_airflow']['url']}",
        ]
    return r


def check_build_commands(root: Path) -> CheckResult:
    """Check 2: Build/test commands declared and runnable."""
    r = CheckResult(
        name="Build & test commands",
        description="AGENTS.md declares concrete build/test commands that exist and run",
        weight=15, blocking=True, passed=False,
        sources=["openai_codex", "github_copilot"],
    )
    agents_md = root / "AGENTS.md"
    if not agents_md.exists():
        r.next_steps = ["First create an AGENTS.md (see Check 1), then declare build/test commands in it."]
        return r

    content = agents_md.read_text(encoding="utf-8", errors="ignore")
    cmd_patterns = [
        r'(?:npm|yarn|pnpm)\s+(?:test|run\s+test|run\s+build)',
        r'(?:make|just)\s+(?:test|build|verify|all)',
        r'(?:go|cargo)\s+(?:test|build)',
        r'python\s+(?:-m\s+)?pytest',
        r'python\s+\S+\.py',
        r'./\S+\s+(?:test|build|verify)',
    ]
    found_cmds = []
    for pattern in cmd_patterns:
        matches = re.findall(pattern, content)
        found_cmds.extend(matches)

    makefile = root / "Makefile"
    justfile = root / "justfile"
    package_json = root / "package.json"

    has_runner = makefile.exists() or justfile.exists() or package_json.exists()
    if found_cmds:
        r.passed = True
        r.details.append(f"Declared commands: {', '.join(set(found_cmds[:5]))}")
        if has_runner:
            r.details.append("Build runner found (Makefile/justfile/package.json)")
    elif has_runner:
        r.passed = True
        r.details.append("Build runner found but not referenced in AGENTS.md")
        r.warnings.append("AGENTS.md should explicitly name the build/test commands agents must use")
        r.next_steps = [
            "Add a 'Build & Test' section to AGENTS.md with the exact commands, e.g.:",
            "  npm test     # run all tests",
            "  npm run build  # build the project",
        ]
    else:
        r.next_steps = [
            "Add a Makefile or justfile with 'test' and 'build' targets,",
            "then reference them in AGENTS.md.",
            "openai/codex uses 'just test' and 'just fmt' as canonical wrappers.",
        ]
    return r


def check_verification_gate(root: Path) -> CheckResult:
    """Check 3: Verification gate before commit/merge."""
    r = CheckResult(
        name="Verification gate",
        description="Documented rule that verification must pass before commit or merge",
        weight=10, blocking=True, passed=False,
        sources=["nist_rmf", "anthropic_multiagent"],
    )
    patterns = [
        r'(?:before|prior\s+to)\s+(?:committ|push|merge|marking.*complete)',
        r'verification?\s+must\s+pass',
        r'(?:never|do\s+not)\s+(?:committ|push|merge)\s+(?:without|until|before)',
        r'(?:githook|pre-committ|husky)',
    ]
    files_to_check = [root / "AGENTS.md", root / ".github" / "pull_request_template.md", root / "CONTRIBUTING.md"]
    found = False
    for f in files_to_check:
        if f.exists():
            content = f.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found = True
                    r.details.append(f"Verification gate mentioned in {f.relative_to(root)}")
                    break
    githooks = root / ".githooks"
    husky = root / ".husky"
    ci_files = list((root / ".github" / "workflows").glob("*.yml")) if (root / ".github" / "workflows").exists() else []
    if githooks.exists() or husky.exists():
        found = True
        r.details.append("Git hooks directory found (.githooks or .husky)")
    if ci_files:
        found = True
        r.details.append(f"CI workflows found: {len(ci_files)}")
    if found:
        r.passed = True
    else:
        r.next_steps = [
            "Add an explicit rule to AGENTS.md or CONTRIBUTING.md:",
            "  'Never commit or merge before verification (npm test) passes.'",
            "Set up a pre-commit hook or CI gate that runs the test suite.",
        ]
    return r


def check_source_registry(root: Path) -> CheckResult:
    """Check 4: Source-of-truth registry for external claims."""
    r = CheckResult(
        name="Source-of-truth registry",
        description="Machine-readable source registry for external claims and references",
        weight=10, blocking=False, passed=False,
        sources=["nist_rmf", "ibm_adlc"],
    )
    candidates = [
        root / "docs" / "research" / "sources.json",
        root / "docs" / "sources.json",
        root / "SOURCES.md",
        root / "docs" / "SOURCES.md",
    ]
    found = [p for p in candidates if p.exists()]
    if found:
        r.passed = True
        r.details.append(f"Source registry: {found[0].relative_to(root)}")
    else:
        r.next_steps = [
            "Create a source registry (e.g., docs/research/sources.json) that",
            "records every external source cited in the repo with a SRC-ID,",
            "URL, and classification (first_party / preprint / standard).",
            "This maps to NIST RMF 'Map' function — knowing what you know and",
            "where it came from.",
        ]
    return r


def check_evidence_traceability(root: Path) -> CheckResult:
    """Check 5: Evidence / traceability for completed work."""
    r = CheckResult(
        name="Evidence & traceability",
        description="Evidence index, traceability matrix, or CI artifacts linking work to verified outcomes",
        weight=10, blocking=False, passed=False,
        sources=["ibm_adlc", "slsa"],
    )
    candidates = [
        root / "factory" / "evidence" / "index.json",
        root / "docs" / "traceability-matrix.md",
        root / "templates" / "traceability-matrix.md",
        root / "evidence",
        root / ".evidence",
        root / "test-results",
        root / ".test-results",
        root / "CHANGELOG.md",
        root / "docs" / "CHANGELOG.md",
    ]
    found = [p for p in candidates if p.exists()]
    ci_dir = root / ".github" / "workflows"
    if ci_dir.exists():
        ci_files = list(ci_dir.glob("*.yml")) + list(ci_dir.glob("*.yaml"))
        if ci_files:
            found.append(ci_dir)
            r.details.append(f"CI workflows: {len(ci_files)} files")
    if found:
        r.passed = True
        if not any("CI workflows" in d for d in r.details):
            r.details.append(f"Evidence system: {found[0].relative_to(root)}")
    else:
        r.next_steps = [
            "Create an evidence trail linking completed work to verification.",
            "Options: a CHANGELOG.md, a factory/evidence/ index, CI workflow",
            "artifacts, or a traceability matrix.",
            "IBM calls this a 'trace layer' — every agent action needs an",
            "accountability trail. SLSA v1.2 provides the standard for",
            "build provenance attestations.",
        ]
    return r


def check_session_ledger(root: Path) -> CheckResult:
    """Check 6: Session ledger / status tracking."""
    r = CheckResult(
        name="Session ledger",
        description="Machine-readable status file, work queue, or changelog for tracking agent sessions",
        weight=5, blocking=False, passed=False,
        sources=["anthropic_multiagent", "ibm_adlc"],
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
    found = [p for p in candidates if p.exists()]
    if found:
        r.passed = True
        r.details.append(f"Session/status tracking: {found[0].relative_to(root)}")
    else:
        r.warnings.append("No session ledger or status file found — agents have no structured record of what they did")
        r.next_steps = [
            "Create a session ledger or status file (e.g., docs/sessions/current.md,",
            "factory/status.json, or CHANGELOG.md) that records the active work",
            "item, last update timestamp, and any blockers.",
        ]
    return r


def check_file_size_discipline(root: Path) -> CheckResult:
    """Check 7: File-size discipline (500/800 LoC thresholds from openai/codex)."""
    r = CheckResult(
        name="File-size discipline",
        description=f"Source files within size thresholds (warn>{WATCH_LOC} LoC, fail>{SMELL_LOC} LoC)",
        weight=10, blocking=False, passed=True,
        sources=["openai_codex"],
    )
    large_files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix not in SOURCE_EXTENSIONS:
            continue
        if "test" in path.name.lower() or "_test" in path.stem.lower() or ".test." in path.name.lower() or path.name.endswith(".test.ts") or path.name.endswith(".test.js"):
            continue
        try:
            loc = sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
        except:
            continue
        if loc >= DEFECT_LOC:
            large_files.append(("DEFECT", path.relative_to(root), loc))
        elif loc >= SMELL_LOC:
            large_files.append(("SMELL", path.relative_to(root), loc))
        elif loc >= WATCH_LOC:
            large_files.append(("WATCH", path.relative_to(root), loc))

    if not large_files:
        r.details.append("All source files within thresholds")
    else:
        r.passed = False
        for level, rel, loc in large_files[:10]:
            r.warnings.append(f"[{level}] {rel} ({loc} LoC)")
        r.next_steps = [
            "openai/codex sets these thresholds in their AGENTS.md:",
            f"  Target: modules under {WATCH_LOC} LoC (excluding tests)",
            f"  Hard cap: files over {SMELL_LOC} LoC must add new functionality",
            f"  in a new module unless there is a documented reason not to.",
            "Consider splitting large files or adding an exemption comment.",
        ]
    return r


def check_agent_attribution(root: Path) -> CheckResult:
    """Check 8: Agent attribution on commits/PRs."""
    r = CheckResult(
        name="Agent attribution",
        description="Convention for attributing AI-assisted commits and PRs (Generated-by / Co-authored-by)",
        weight=5, blocking=False, passed=False,
        sources=["apache_airflow"],
    )
    patterns = [
        r'Generated-by:',
        r'Co-authored-by:',
        r'Drafted-by:',
        r'AI-assisted',
        r'agent-assisted',
    ]
    files_to_check = [root / "AGENTS.md", root / ".github" / "pull_request_template.md", root / "CONTRIBUTING.md"]
    found = False
    for f in files_to_check:
        if f.exists():
            content = f.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found = True
                    r.details.append(f"Attribution convention in {f.relative_to(root)}")
                    break
    if found:
        r.passed = True
    else:
        r.next_steps = [
            "Add an attribution convention to AGENTS.md or PR template:",
            '  Generated-by: <Agent Name and Version>',
            "apache/airflow uses Generated-by in PR bodies and Drafted-by",
            "in agent-posted GitHub messages.",
        ]
    return r


def check_security_never_rules(root: Path) -> CheckResult:
    """Check 9: Security 'Never' rules in agent policy."""
    r = CheckResult(
        name="Security Never-rules",
        description="AGENTS.md or SECURITY.md enumerates hard 'Never' rules for agents",
        weight=10, blocking=True, passed=False,
        sources=["nist_rmf", "apache_airflow"],
    )
    files_to_check = [root / "AGENTS.md", root / "SECURITY.md", root / ".github" / "SECURITY.md"]
    never_count = 0
    for f in files_to_check:
        if f.exists():
            content = f.read_text(encoding="utf-8", errors="ignore")
            never_count += len(re.findall(r'\b[Nn]ever\b', content))
    if never_count >= 5:
        r.passed = True
        r.details.append(f"Found {never_count} 'Never' rules across policy files")
    elif never_count >= 1:
        r.passed = True
        r.details.append(f"Found {never_count} 'Never' rule(s) — recommend at least 5")
        r.warnings.append("Consider adding more explicit 'Never' rules for security boundaries")
        r.next_steps = [
            "Add more 'Never' rules to AGENTS.md or SECURITY.md, e.g.:",
            "  Never commit secrets, API keys, or credentials",
            "  Never expose the Docker socket to construction agents",
            "  Never use destructive git operations without explicit request",
            "  Never weaken security policy to make a check pass",
            "  Never skip the verification gate before commit",
        ]
    else:
        r.next_steps = [
            "Add a 'Never' rules section to AGENTS.md or SECURITY.md.",
            "apache/airflow's AGENTS.md has an exemplary 'Boundaries' section",
            "with explicit 'Never' rules for agents.",
        ]
    return r


def check_independent_review(root: Path) -> CheckResult:
    """Check 10: Independent review requirement."""
    r = CheckResult(
        name="Independent review",
        description="Documented requirement for independent review before commit",
        weight=5, blocking=False, passed=False,
        sources=["anthropic_multiagent", "nist_rmf"],
    )
    patterns = [
        r'(?:independent|rubberduck|peer|code)\s+review',
        r'review\s+(?:before|prior\s+to)\s+(?:committ|merge|push)',
        r'self-review.*review',
    ]
    files_to_check = [root / "AGENTS.md", root / "CONTRIBUTING.md", root / ".github" / "pull_request_template.md", root / "REVIEW.md"]
    found = False
    for f in files_to_check:
        if f.exists():
            content = f.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found = True
                    r.details.append(f"Review requirement in {f.relative_to(root)}")
                    break
    if found:
        r.passed = True
    else:
        r.next_steps = [
            "Add an independent review requirement to AGENTS.md:",
            "  'Before committing: complete self-review, then independent",
            "  (rubberduck) review, then rerun verification, then commit.'",
            "Anthropic's research shows human evaluation catches what",
            "automation misses.",
        ]
    return r


def check_cyclic_verification(root: Path) -> CheckResult:
    """Check 11: Cyclic verification loop (plan→build→verify→fix→verify)."""
    r = CheckResult(
        name="Cyclic verification",
        description="Workflow loops: plan → build → verify → fix → verify until pass",
        weight=5, blocking=False, passed=False,
        sources=["anthropic_multiagent"],
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
            content = f.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found = True
                    r.details.append(f"Cyclic verification in {f.relative_to(root)}")
                    break
    if found:
        r.passed = True
    else:
        r.next_steps = [
            "Document a cyclic verification loop in AGENTS.md:",
            "  plan → build → verify → (if fail) fix → verify again → review",
            "Anthropic's multi-agent system uses iterative subagent loops",
            "with interleaved thinking after each tool result.",
        ]
    return r


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_score(results: list[CheckResult]) -> tuple[int, str, bool]:
    total_weight = sum(r.weight for r in results)
    earned = sum(r.weight for r in results if r.passed)
    score = round(earned / total_weight * 100) if total_weight > 0 else 0
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "E"
    gate_passed = all(r.passed for r in results if r.blocking)
    return score, grade, gate_passed


GRADE_LABELS = {
    "A": "Governance-Optimized",
    "B": "Managed",
    "C": "Defined",
    "D": "Repeatable",
    "E": "Initial / Absent",
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_agent_policy,
    check_build_commands,
    check_verification_gate,
    check_source_registry,
    check_evidence_traceability,
    check_session_ledger,
    check_file_size_discipline,
    check_agent_attribution,
    check_security_never_rules,
    check_independent_review,
    check_cyclic_verification,
]


def run_audit(root: Path) -> tuple[list[CheckResult], int, str, bool]:
    results = [check(root) for check in ALL_CHECKS]
    score, grade, gate = compute_score(results)
    return results, score, grade, gate


def format_report(root: Path, results: list[CheckResult], score: int, grade: str, gate: bool) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  Rung — AI Agent Governance Audit")
    lines.append("=" * 60)
    lines.append(f"  Repository: {root}")
    lines.append(f"  Score: {score}/100  Grade: {grade} ({GRADE_LABELS[grade]})")
    lines.append(f"  Quality Gate: {'PASS' if gate else 'FAIL'}")
    lines.append("=" * 60)
    lines.append("")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        blocking_tag = " [blocking]" if r.blocking else ""
        lines.append(f"  [{status}] {r.name} ({r.weight} pts){blocking_tag}")
        lines.append(f"         {r.description}")
        for d in r.details:
            lines.append(f"         → {d}")
        for w in r.warnings:
            lines.append(f"         ⚠ {w}")
        if r.sources:
            src_refs = [SOURCES[s]["name"] for s in r.sources if s in SOURCES]
            lines.append(f"         Sources: {', '.join(src_refs)}")
        if not r.passed and r.next_steps:
            lines.append("         Next steps:")
            for step in r.next_steps:
                lines.append(f"           {step}")
        lines.append("")

    lines.append("-" * 60)
    lines.append(f"  Score: {score}/100  Grade: {grade} ({GRADE_LABELS[grade]})")
    lines.append(f"  Quality Gate: {'PASS' if gate else 'FAIL'}")
    failed_blocking = [r for r in results if r.blocking and not r.passed]
    if failed_blocking:
        lines.append(f"  Blocking failures: {len(failed_blocking)}")
        for r in failed_blocking:
            lines.append(f"    - {r.name}")
    lines.append("")
    lines.append("  Cited sources:")
    all_sources = set()
    for r in results:
        all_sources.update(r.sources)
    for key in sorted(all_sources):
        if key in SOURCES:
            s = SOURCES[key]
            lines.append(f"    [{key}] {s['name']}")
            lines.append(f"      {s['url']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rung CLI — AI Agent Governance Audit")
    parser.add_argument("--root", default=".", help="Repository root to audit")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    results, score, grade, gate = run_audit(root)

    if args.json:
        output = {
            "repository": str(root),
            "score": score,
            "grade": grade,
            "grade_label": GRADE_LABELS[grade],
            "quality_gate": "PASS" if gate else "FAIL",
            "checks": [
                {
                    "name": r.name,
                    "description": r.description,
                    "weight": r.weight,
                    "blocking": r.blocking,
                    "passed": r.passed,
                    "warnings": r.warnings,
                    "details": r.details,
                    "sources": [SOURCES[s]["name"] for s in r.sources if s in SOURCES],
                    "next_steps": r.next_steps,
                }
                for r in results
            ],
            "sources": {k: v for k, v in SOURCES.items()},
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_report(root, results, score, grade, gate))

    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())