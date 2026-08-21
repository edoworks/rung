"""Core data models for the Rung audit engine.

Defines evidence states, confidence levels, source classifications,
authority recommendations, and the CheckResult dataclass that every
check returns. Replaces the boolean-only pass/fail model with a
six-state evidence maturity model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EvidenceState(str, Enum):
    """Six-state evidence maturity model replacing boolean pass/fail."""
    ABSENT = "absent"
    CLAIMED = "claimed"
    DETECTED = "detected"
    ENFORCED = "enforced"
    VERIFIED = "verified"
    UNOBSERVABLE = "unobservable"


class Confidence(str, Enum):
    """Per-finding confidence level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceClass(str, Enum):
    """Source authority classification."""
    STANDARD = "standard"
    PLATFORM_CONTROL = "platform_control"
    VENDOR_GUIDANCE = "vendor_guidance"
    INDUSTRY_PRACTICE = "industry_practice"
    EXEMPLAR = "exemplar"
    EDOWORKS_POLICY = "edoworks_policy"


class AuthorityLevel(str, Enum):
    """Maximum recommended agent authority based on public evidence.

    A public-only report must never recommend autonomous merge or release
    when enforcement settings are unobservable.
    """
    UNSAFE = "unsafe"
    LOCAL_ONLY = "local_only"
    PR_ONLY_PROVISIONAL = "pr_only_provisional"
    OWNER_EVIDENCE_REQUIRED = "owner_evidence_required"


@dataclass
class CheckResult:
    """Result of a single governance check.

    Replaces the boolean-only model. Every check returns an evidence state,
    confidence, blocking authority, evidence snippets, limitations,
    remediation steps, and source mappings.
    """
    name: str
    description: str
    weight: int
    blocking: bool
    state: EvidenceState
    confidence: Confidence = Confidence.MEDIUM
    blocking_for: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)
    source_mappings: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Backward compatibility: a check 'passes' if its state is
        detected, enforced, or verified. Absent, claimed, and unobservable
        do not pass. Blocking checks must pass for the quality gate."""
        return self.state in (
            EvidenceState.DETECTED,
            EvidenceState.ENFORCED,
            EvidenceState.VERIFIED,
        )


@dataclass
class AuditResult:
    """Canonical immutable audit result (AuditResult v1).

    The free preview and paid PDF both render from this same object.
    Includes a report-data digest field that is computed over the
    canonical JSON of all other fields (excluding the digest itself).
    """
    repository: str
    commit_sha: Optional[str]
    checks: list[CheckResult]
    score: int
    grade: str
    grade_label: str
    quality_gate: str
    authority: AuthorityLevel
    rung_version: str
    schema_version: str
    timestamp: str
    report_data_sha256: Optional[str] = None