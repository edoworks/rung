# fake_ci_echo_only fixture: has a CI workflow that echoes success but runs no tests.
# Positive for: verification_gate CI existence (DETECTED at most)
# Negative/deceptive: CI does NOT run tests, so it should NOT get verification or traceability credit