"""Rung — AI Agent Governance Audit Engine.

Modular audit engine for scoring repository readiness for AI coding
agent governance. Produces a deterministic AuditResult v1 from which
both free preview and paid PDF projections render.

License: MIT
"""

__version__ = "0.2.0"

from rung.audit import run_audit, AuditResult
from rung.scoring import compute_score, GRADE_LABELS
from rung.models import CheckResult, EvidenceState, Confidence, SourceClass, AuthorityLevel
from rung.renderer import render_preview, render_html, render_pdf_data

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
    "render_preview",
    "render_html",
    "render_pdf_data",
]