"""Scoring and authority recommendation engine.

Computes a numeric score (0-100), letter grade (A-E), quality gate
verdict, and maximum recommended agent authority from check results.
File-size discipline is excluded from the governance score and appears
only in a non-scoring maintainability appendix.
"""

from rung.models import CheckResult, EvidenceState, AuthorityLevel

GRADE_LABELS = {
    "A": "Governance-Optimized",
    "B": "Managed",
    "C": "Defined",
    "D": "Repeatable",
    "E": "Initial / Absent",
}


def compute_score(results: list[CheckResult]) -> tuple[int, str, bool]:
    """Compute score, grade, and gate from check results.

    Only checks with a weight > 0 contribute to the score. File-size
    discipline checks should have weight=0 to appear in the report
    without affecting the governance score.
    """
    scoring_checks = [r for r in results if r.weight > 0]
    total_weight = sum(r.weight for r in scoring_checks)
    earned = sum(r.weight for r in scoring_checks if r.passed)
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

    gate_passed = all(r.passed for r in scoring_checks if r.blocking)
    return score, grade, gate_passed


def recommend_authority(results: list[CheckResult]) -> AuthorityLevel:
    """Recommend maximum agent authority based on evidence states.

    A public-only report must never recommend autonomous merge or release
    when enforcement settings are unobservable. Authority is capped by
    the weakest blocking evidence state.
    """
    has_unobservable = False
    has_claimed_only = False
    has_detected = False
    has_enforced = False

    for r in results:
        if not r.blocking or r.weight == 0:
            continue
        if r.state == EvidenceState.UNOBSERVABLE:
            has_unobservable = True
        elif r.state == EvidenceState.ABSENT:
            return AuthorityLevel.UNSAFE
        elif r.state == EvidenceState.CLAIMED:
            has_claimed_only = True
        elif r.state == EvidenceState.DETECTED:
            has_detected = True
        elif r.state == EvidenceState.ENFORCED:
            has_enforced = True
        elif r.state == EvidenceState.VERIFIED:
            has_enforced = True

    if has_unobservable:
        return AuthorityLevel.OWNER_EVIDENCE_REQUIRED
    if has_claimed_only:
        return AuthorityLevel.UNSAFE
    if has_detected and not has_enforced:
        return AuthorityLevel.PR_ONLY_PROVISIONAL
    if has_enforced:
        return AuthorityLevel.LOCAL_ONLY
    return AuthorityLevel.UNSAFE