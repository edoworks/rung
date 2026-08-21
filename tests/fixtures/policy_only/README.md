# policy_only fixture: has AGENTS.md with policy text but no CI, no tests, no enforcement.
# Positive for: agent_policy check (DETECTED)
# Negative for: verification_gate (should not get enforcement credit), evidence_traceability (no CI artifacts)
# Deceptive: AGENTS.md mentions "verification must pass" but there is no CI or hooks