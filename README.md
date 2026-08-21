# Rung — AI Agent Governance Audit

Score your repository's readiness for AI coding agent governance.

Rung checks 11 governance dimensions using a six-state evidence maturity
model (absent, claimed, detected, enforced, verified, unobservable), produces
a numeric score (0–100), a letter grade (A–E), a quality gate verdict
(PASS/FAIL), a maximum recommended agent authority, and actionable next
steps for each gap found.

## Quick start

```bash
# Clone
git clone https://github.com/edoworks/rung.git
cd rung

# Run against your repo
python3 -m rung --root /path/to/your/repo

# JSON output for CI
python3 -m rung --root /path/to/your/repo --json

# Dependency-free standalone artifact
python3 rung-cli.py --root /path/to/your/repo --json
```

## What it checks

| # | Check | Weight | Blocking? | Source |
|---|-------|--------|-----------|--------|
| 1 | Agent policy file (AGENTS.md) | 15 | Yes | [agents.md](https://agents.md), [GitHub Copilot docs](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot) |
| 2 | Build & test commands declared | 15 | Yes | [openai/codex AGENTS.md](https://github.com/openai/codex/blob/main/AGENTS.md) |
| 3 | Verification gate before commit | 10 | Yes | [NIST AI RMF](https://nist.gov/itl/ai-risk-management-framework), [Anthropic multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system) |
| 4 | Source-of-truth registry | 10 | No | NIST AI RMF, [IBM ADLC](https://www.ibm.com/think/topics/agent-development-lifecycle-adlc) |
| 5 | Evidence & traceability | 10 | No | IBM ADLC, [SLSA v1.2](https://slsa.dev/spec/v1.2/) |
| 6 | Session ledger / status | 5 | No | Anthropic, IBM ADLC |
| 7 | File-size discipline (non-scoring) | 0 | No | openai/codex AGENTS.md |
| 8 | Agent attribution (Generated-by) | 5 | No | [apache/airflow AGENTS.md](https://github.com/apache/airflow/blob/main/AGENTS.md) |
| 9 | Security "Never" rules | 10 | Yes | NIST AI RMF, apache/airflow |
| 10 | Independent review requirement | 5 | No | Anthropic, NIST AI RMF |
| 11 | Cyclic verification loop | 5 | No | Anthropic multi-agent |

**Total: 100 points** (file-size discipline is non-scoring). Quality gate
passes only if all blocking checks reach at least `detected` state.

## Evidence states

Every check returns one of six evidence states instead of boolean pass/fail:

| State | Meaning |
|-------|---------|
| `absent` | Not found at all |
| `claimed` | Documented but not confirmed by evidence |
| `detected` | Found in public repository contents |
| `enforced` | Confirmed as enforced (requires owner permissions) |
| `verified` | Independently verified (requires owner permissions) |
| `unobservable` | Cannot be determined from public evidence alone |

## Authority recommendations

Based on evidence states, Rung recommends a maximum agent authority:

| Level | Meaning |
|-------|---------|
| `unsafe` | Do not use autonomous agents |
| `local_only` | Local changes only, no push/merge |
| `pr_only_provisional` | Pull requests only, not autonomous merge |
| `owner_evidence_required` | Cannot verify enforcement from public evidence |

## Scoring

| Grade | Score | Label |
|-------|-------|-------|
| A | ≥ 90 | Governance-Optimized |
| B | 80–89 | Managed |
| C | 70–79 | Defined |
| D | 60–69 | Repeatable |
| E | < 60 | Initial / Absent |

## Install

### From source

```bash
git clone https://github.com/edoworks/rung.git
cd rung
python3 -m rung --root .
```

### Standalone artifact

`rung-cli.py` is generated from the canonical modular package and runs with
Python 3.10+ without installation or third-party dependencies. Contributors
must regenerate and verify it after changing `rung/`:

```bash
python3 scripts/build_single_file.py
python3 scripts/build_single_file.py --check
```

The generator embeds a digest of all package sources and emits deterministic
bytes. Do not edit `rung-cli.py` directly.

## Use in CI

```yaml
# .github/workflows/governance-audit.yml
name: Governance Audit
on: [pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Run Rung governance audit
        run: |
          pip install -e .
          python3 -m rung --root . --json > audit.json
          SCORE=$(python3 -c "import json; print(json.load(open('audit.json'))['score'])")
          echo "Governance score: $SCORE/100"
          if [ "$SCORE" -lt 70 ]; then echo "::error::Governance score below threshold (70)"; exit 1; fi
```

## Cited sources

Rung is informed by standards and industry practices. Not every check is
directly derived from a standard.

- [agents.md](https://agents.md) — Linux Foundation / AAIF cross-vendor agent policy spec
- [GitHub Copilot repository custom instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
- [NIST AI Risk Management Framework 1.0](https://nist.gov/itl/ai-risk-management-framework)
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [openai/codex AGENTS.md](https://github.com/openai/codex/blob/main/AGENTS.md) — 500/800 LoC thresholds
- [apache/airflow AGENTS.md](https://github.com/apache/airflow/blob/main/AGENTS.md) — Generated-by attribution, Never-rules
- [IBM — Agent Development Lifecycle](https://www.ibm.com/think/topics/agent-development-lifecycle-adlc)
- [SLSA v1.2](https://slsa.dev/spec/v1.2/) — Supply-chain Levels for Software Artifacts
- [ISO/IEC 42001:2023](https://www.iso.org/standard/83730.html) — AI management system standard
- [OpenSSF Scorecard](https://scorecard.dev/) — Check-specific risk explanation model

## Limitations

A public, accountless scan cannot inspect some important enforcement
settings. GitHub's branch-protection API requires Administration read
permission, even for reads on public repositories. Rung therefore labels
these controls as `unobservable` rather than passing or failing them.

Rung is an automated public-evidence assessment. It is not certification,
compliance, or legal advice.

## Sponsor

If Rung helps your team, consider [sponsoring on GitHub](https://github.com/sponsors/edoworks).

## License

MIT
