# Rung — Agent Map

Rung is an open-source audit engine that scores repositories for AI agent
governance readiness. It uses a six-state evidence maturity model
(absent, claimed, detected, enforced, verified, unobservable) rather than
boolean pass/fail.

## Build & Test

```bash
# Run tests
python3 -m pytest tests/

# Run the CLI against your repo
python3 -m rung --root .

# JSON output for CI
python3 -m rung --root . --json

# Verify generated standalone artifact
python3 scripts/build_single_file.py --check
```

## Code Style

- Python 3.10+ (dataclasses, type hints, enums)
- No external dependencies (stdlib only)
- MIT-licensed

## Security

- Never transmit repository contents to external services
- Never execute arbitrary code from the repository being audited
- Never weaken check thresholds to make a check pass
- Never commit secrets, credentials, or signing keys
- Never skip `python3 -m pytest tests/` before commit or merge

## Testing

The CLI is validated against adversarial fixtures in tests/fixtures/:
- excellent_public_evidence (positive)
- policy_only (deceptive: claims verification but no CI)
- fake_ci_echo_only (deceptive: CI exists but runs no tests)
- no_never_rules (negative: empty repo)

`tests/test_checks_adversarial.py` also exercises positive, negative, and
deceptive states for every registered check.
