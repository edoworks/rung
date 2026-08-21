"""Evidence collection helpers for Rung checks.

Provides utilities for reading files, searching for patterns, and
detecting CI workflow semantics without giving false credit for
workflow existence alone.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from rung.sources import IGNORED_PARTS


def read_text(path: Path) -> Optional[str]:
    """Read a file as UTF-8 text, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def find_file(root: Path, candidates: list[Path]) -> list[Path]:
    """Return existing files from a list of candidate paths."""
    return [p for p in candidates if p.exists()]


def count_pattern(content: str, pattern: str) -> int:
    """Count regex matches in content (case-insensitive)."""
    return len(re.findall(pattern, content, re.IGNORECASE))


def has_pattern(content: str, pattern: str) -> bool:
    """Check if content matches a regex pattern (case-insensitive)."""
    return bool(re.search(pattern, content, re.IGNORECASE))


def has_ci_workflows(root: Path) -> bool:
    """Check if .github/workflows directory exists and has .yml/.yaml files."""
    ci_dir = root / ".github" / "workflows"
    if not ci_dir.exists():
        return False
    return bool(list(ci_dir.glob("*.yml")) or list(ci_dir.glob("*.yaml")))


def ci_workflow_runs_tests(root: Path) -> bool:
    """Semantic inspection: do CI workflows actually run tests?

    Reads workflow YAML files and checks for test-related step content.
    Finding any .github/workflows/*.yml does NOT automatically give credit.
    The workflow must contain test-related commands.
    """
    ci_dir = root / ".github" / "workflows"
    if not ci_dir.exists():
        return False
    test_patterns = [
        r"(?:npm|yarn|pnpm)\s+(?:test|run\s+test)",
        r"(?:make|just)\s+test",
        r"(?:go|cargo)\s+test",
        r"python3?\s+(?:-m\s+)?pytest",
        r"python3?\s+\S+\.py.*test",
        r"\bpytest\b",
        r"\bunittest\b",
        r"\bjest\b",
        r"\bvitest\b",
    ]
    for wf_file in list(ci_dir.glob("*.yml")) + list(ci_dir.glob("*.yaml")):
        content = read_text(wf_file)
        if content is None:
            continue
        for pattern in test_patterns:
            if has_pattern(content, pattern):
                return True
    return False


def ci_workflow_enforces_gate(root: Path) -> bool:
    """Semantic inspection: does CI enforce required status checks?

    Reads workflow YAML for branch protection hints. Note: actual branch
    protection rules are not observable from public repository contents
    without Administration read permission. This function only checks
    whether workflows reference required status checks or protection
    language. It does NOT claim enforcement.
    """
    ci_dir = root / ".github" / "workflows"
    if not ci_dir.exists():
        return False
    enforcement_patterns = [
        r"required_status_checks",
        r"branch_protection",
        r"enforce_admins",
        r"required_pull_request_reviews",
    ]
    for wf_file in list(ci_dir.glob("*.yml")) + list(ci_dir.glob("*.yaml")):
        content = read_text(wf_file)
        if content is None:
            continue
        for pattern in enforcement_patterns:
            if has_pattern(content, pattern):
                return True
    return False


def detect_build_commands(content: str) -> list[str]:
    """Detect build/test commands in AGENTS.md or similar file content.

    Recognizes python3 (not just python), python -m, shell scripts, make,
    just, and package-manager commands.
    """
    cmd_patterns = [
        r'(?:npm|yarn|pnpm)\s+(?:test|run\s+test|run\s+build)',
        r'(?:make|just)\s+(?:test|build|verify|all)',
        r'(?:go|cargo|rustc)\s+(?:test|build)',
        r'python3\s+(?:-m\s+)?(?:pytest|unittest)',
        r'python3\s+\S+\.py',
        r'python\s+(?:-m\s+)?(?:pytest|unittest)',
        r'python\s+\S+\.py',
        r'\./\S+\s+(?:test|build|verify)',
        r'ruby\s+(?:-I\S+\s+)?\S+test\S*',
        r'dotnet\s+(?:test|build)',
    ]
    found = []
    for pattern in cmd_patterns:
        matches = re.findall(pattern, content)
        found.extend(matches)
    return list(set(found))


def count_source_loc(path: Path) -> int:
    """Count lines of code in a source file, excluding tests."""
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
    except Exception:
        return 0


def is_test_file(path: Path) -> bool:
    """Check if a path is a test file by name conventions."""
    name = path.name.lower()
    stem = path.stem.lower()
    return (
        "test" in name
        or "_test" in stem
        or ".test." in name
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
    )