"""Rung governance checks.

Each check returns a CheckResult with evidence states instead of
boolean pass/fail. Checks are registered in ALL_CHECKS.
"""

from rung.checks.agent_policy import check_agent_policy
from rung.checks.build_commands import check_build_commands
from rung.checks.verification_gate import check_verification_gate
from rung.checks.source_registry import check_source_registry
from rung.checks.evidence_traceability import check_evidence_traceability
from rung.checks.session_ledger import check_session_ledger
from rung.checks.file_size import check_file_size
from rung.checks.agent_attribution import check_agent_attribution
from rung.checks.security_never_rules import check_security_never_rules
from rung.checks.independent_review import check_independent_review
from rung.checks.cyclic_verification import check_cyclic_verification

ALL_CHECKS = [
    check_agent_policy,
    check_build_commands,
    check_verification_gate,
    check_source_registry,
    check_evidence_traceability,
    check_session_ledger,
    check_file_size,
    check_agent_attribution,
    check_security_never_rules,
    check_independent_review,
    check_cyclic_verification,
]