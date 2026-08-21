"""Audit orchestrator — runs all checks and produces AuditResult v1.

The free preview and paid PDF both render from the same AuditResult.
Includes a canonical report-data digest computed over all fields
except the digest itself.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rung.models import CheckResult, AuditResult, AuthorityLevel
from rung.scoring import compute_score, recommend_authority, GRADE_LABELS
from rung.checks import ALL_CHECKS
from rung import __version__ as RUNG_VERSION

SCHEMA_VERSION = "1.0.0"


def _compute_digest(result_dict: dict) -> str:
    """Compute SHA-256 over canonical JSON of the result, excluding the digest field."""
    data = {k: v for k, v in result_dict.items() if k != "report_data_sha256"}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_audit(
    root: Path,
    commit_sha: Optional[str] = None,
    repository: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> AuditResult:
    """Run all checks against a repository root and return AuditResult v1."""
    root = Path(root).resolve()
    checks = [check(root) for check in ALL_CHECKS]
    score, grade, gate = compute_score(checks)
    authority = recommend_authority(checks)
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = AuditResult(
        repository=repository or str(root),
        commit_sha=commit_sha,
        checks=checks,
        score=score,
        grade=grade,
        grade_label=GRADE_LABELS.get(grade, ""),
        quality_gate="PASS" if gate else "FAIL",
        authority=authority,
        rung_version=RUNG_VERSION,
        schema_version=SCHEMA_VERSION,
        timestamp=timestamp,
    )

    result_dict = result_to_dict(result)
    result.report_data_sha256 = _compute_digest(result_dict)
    return result


def result_to_dict(result: AuditResult) -> dict:
    """Convert AuditResult to a JSON-serializable dict."""
    return {
        "repository": result.repository,
        "commit_sha": result.commit_sha,
        "score": result.score,
        "grade": result.grade,
        "grade_label": result.grade_label,
        "quality_gate": result.quality_gate,
        "authority": result.authority.value if isinstance(result.authority, AuthorityLevel) else str(result.authority),
        "rung_version": result.rung_version,
        "schema_version": result.schema_version,
        "timestamp": result.timestamp,
        "report_data_sha256": result.report_data_sha256,
        "checks": [check_to_dict(c) for c in result.checks],
    }


def check_to_dict(c: CheckResult) -> dict:
    """Convert CheckResult to a JSON-serializable dict."""
    return {
        "name": c.name,
        "description": c.description,
        "weight": c.weight,
        "blocking": c.blocking,
        "state": c.state.value if hasattr(c.state, "value") else str(c.state),
        "confidence": c.confidence.value if hasattr(c.confidence, "value") else str(c.confidence),
        "blocking_for": c.blocking_for,
        "evidence": c.evidence,
        "limitations": c.limitations,
        "remediation": c.remediation,
        "source_mappings": c.source_mappings,
        "passed": c.passed,
    }
