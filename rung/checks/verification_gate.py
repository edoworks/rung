"""Check 3: Verification gate before commit/merge.

Does not give credit merely for finding any .github/workflows file.
Workflow existence is detected at most; enforcement requires semantic
inspection or is unobservable from public evidence.
"""
from pathlib import Path
from rung.models import CheckResult, EvidenceState, Confidence
from rung.sources import SOURCES
from rung.evidence import read_text, has_affirmative_pattern, has_ci_workflows, ci_workflow_runs_tests, ci_workflow_enforces_gate


def check_verification_gate(root: Path) -> CheckResult:
    r = CheckResult(
        name="Verification gate",
        description="Documented rule that verification must pass before commit or merge",
        weight=10, blocking=True,
        state=EvidenceState.ABSENT,
        confidence=Confidence.MEDIUM,
        blocking_for=["merge", "release"],
        source_mappings=[
            {"id": "nist_rmf", "classification": SOURCES["nist_rmf"]["classification"].value},
            {"id": "anthropic_multiagent", "classification": SOURCES["anthropic_multiagent"]["classification"].value},
        ],
    )
    patterns = [
        r'(?:before|prior\s+to)\s+(?:commit|push|merge|marking.*complete)',
        r'verification?\s+must\s+pass',
        r'(?:never|do\s+not)\s+(?:commit|push|merge)\s+(?:without|until|before)',
        r'(?:githook|pre-commit|husky)',
    ]
    files_to_check = [root / "AGENTS.md", root / ".github" / "pull_request_template.md", root / "CONTRIBUTING.md"]
    documented = False
    for f in files_to_check:
        if f.exists():
            content = read_text(f)
            if content is None:
                continue
            if has_affirmative_pattern(content, patterns):
                documented = True
                r.evidence.append(f"Verification gate mentioned in {f.relative_to(root)}")

    githooks = root / ".githooks"
    husky = root / ".husky"
    has_hooks = any(path.is_dir() and any(child.is_file() for child in path.iterdir()) for path in (githooks, husky))
    if has_hooks:
        documented = True
        r.evidence.append("Git hooks directory found (.githooks or .husky)")

    ci_exists = has_ci_workflows(root)
    ci_runs_tests = ci_workflow_runs_tests(root)
    ci_enforces = ci_workflow_enforces_gate(root)

    if ci_exists:
        if ci_enforces:
            r.evidence.append("CI workflow references enforcement settings")
        elif ci_runs_tests:
            r.evidence.append("CI workflow detected running tests (not necessarily enforced)")
        else:
            r.evidence.append("CI workflow file found but does not appear to run tests")
            r.limitations.append("Workflow existence alone is not enforcement; the workflow must run tests and be required")

    if documented and ci_runs_tests:
        r.state = EvidenceState.UNOBSERVABLE
        r.limitations.append("Actual enforcement (required status checks, branch protection) is not observable from public repository contents without Administration read permission")
    elif documented or has_hooks:
        r.state = EvidenceState.CLAIMED
        r.limitations.append("Verification gate is documented but not confirmed as enforced by CI")
    elif ci_exists and not ci_runs_tests:
        r.state = EvidenceState.CLAIMED
        r.limitations.append("CI exists but does not run tests; this is not a verification gate")
    else:
        r.remediation = [
            "Add an explicit rule to AGENTS.md or CONTRIBUTING.md:",
            "  'Never commit or merge before verification (npm test) passes.'",
            "Set up a pre-commit hook or CI gate that runs the test suite.",
        ]
    return r
