"""Rung — AI Agent Governance Audit Engine.

Modular audit engine for scoring repository readiness for AI coding
agent governance. Produces a deterministic AuditResult v1 from which
both free preview and paid PDF projections render.

License: MIT
"""

__version__ = "0.3.0"

from rung.audit import run_audit, AuditResult
from rung.scoring import compute_score, GRADE_LABELS
from rung.models import CheckResult, EvidenceState, Confidence, SourceClass, AuthorityLevel

__all__ = [
    "run_audit",
    "AuditResult",
    "compute_score",
    "GRADE_LABELS",
    "CheckResult",
    "EvidenceState",
    "Confidence",
    "SourceClass",
    "AuthorityLevel",
]
