# Rung — AI Agent Governance Audit

Score your repository's readiness for AI coding agent governance.

Rung checks 11 governance dimensions derived from published standards and industry best practices, produces a numeric score (0–100), a letter grade (A–E), a quality gate verdict (PASS/FAIL), and actionable next steps for each gap found.

## Quick start

```bash
# Download
curl -O https://raw.githubusercontent.com/edoworks/rung/main/rung-cli.py

# Run against your repo
python3 rung-cli.py --root /path/to/your/repo

# JSON output for CI
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
| 7 | File-size discipline (500/800 LoC) | 10 | No | openai/codex AGENTS.md |
| 8 | Agent attribution (Generated-by) | 5 | No | [apache/airflow AGENTS.md](https://github.com/apache/airflow/blob/main/AGENTS.md) |
| 9 | Security "Never" rules | 10 | Yes | NIST AI RMF, apache/airflow |
| 10 | Independent review requirement | 5 | No | Anthropic, NIST AI RMF |
| 11 | Cyclic verification loop | 5 | No | Anthropic multi-agent |

**Total: 100 points.** Quality gate passes only if all blocking checks pass.

## Scoring

| Grade | Score | Label |
|-------|-------|-------|
| A | ≥ 90 | Governance-Optimized |
| B | 80–89 | Managed |
| C | 70–79 | Defined |
| D | 60–69 | Repeatable |
| E | < 60 | Initial / Absent |

## Validated against real repos

| Repo | Score | Grade | Gate |
|------|-------|-------|------|
| [sf0.5](https://github.com/hellofoculoom/sf0.5) (Verifiable Software Factory) | 80/100 | B | PASS |
| [openai/codex](https://github.com/openai/codex) | 70/100 | C | PASS |
| [apache/airflow](https://github.com/apache/airflow) | 70/100 | C | PASS |
| [danshapiro/trycycle](https://github.com/danshapiro/trycycle) | 30/100 | E | FAIL |
| [strongdm/comply](https://github.com/strongdm/comply) | 0/100 | E | FAIL |

## Case study: Forking trycycle and improving its score

We forked [danshapiro/trycycle](https://github.com/danshapiro/trycycle) (the tool that inspired our factory's trycycle loop) and applied Rung's recommendations to demonstrate the CLI's value.

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Score | 30/100 | 90/100 | **+60** |
| Grade | E (Initial) | A (Governance-Optimized) | **+4 levels** |
| Quality Gate | FAIL | PASS | **Fixed** |

7 governance improvements were applied — each directly from a Rung CLI recommendation with cited sources. No code was changed; all fixes were documentation, CI, and build infrastructure. See the full analysis at [edoworks/trycycle/GOVERNANCE_AUDIT.md](https://github.com/edoworks/trycycle/blob/main/GOVERNANCE_AUDIT.md).

## Cited sources

- [agents.md](https://agents.md) — Linux Foundation / AAIF cross-vendor agent policy spec (60k+ repos)
- [GitHub Copilot repository custom instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
- [NIST AI Risk Management Framework 1.0](https://nist.gov/itl/ai-risk-management-framework)
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [openai/codex AGENTS.md](https://github.com/openai/codex/blob/main/AGENTS.md) — 500/800 LoC thresholds
- [apache/airflow AGENTS.md](https://github.com/apache/airflow/blob/main/AGENTS.md) — Generated-by attribution, Never-rules
- [IBM — Agent Development Lifecycle](https://www.ibm.com/think/topics/agent-development-lifecycle-adlc)
- [SLSA v1.2](https://slsa.dev/spec/v1.2/) — Supply-chain Levels for Software Artifacts
- [ISO/IEC 42001:2023](https://www.iso.org/standard/83730.html) — AI management system standard

## Install

### Direct download

```bash
curl -O https://raw.githubusercontent.com/edoworks/rung/main/rung-cli.py
chmod +x rung-cli.py
```

### Clone

```bash
git clone https://github.com/edoworks/rung.git
```

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
      - run: python3 https://raw.githubusercontent.com/edoworks/rung/main/rung-cli.py --root . --json > audit.json
      - run: |
          SCORE=$(python3 -c "import json; print(json.load(open('audit.json'))['score'])")
          echo "Governance score: $SCORE/100"
          if [ "$SCORE" -lt 70 ]; then echo "::error::Governance score below threshold (70)"; exit 1; fi
```

## Sponsor

If Rung helps your team, consider [sponsoring on GitHub](https://github.com/sponsors/edoworks).

| Tier | Price | What you get |
|------|-------|-------------|
| Supporter | $5/month | Name in README, sponsor badge |
| Advocate | $25/month | Logo in README, early access to new checks |
| Partner | $100/month | Logo on rung.edoworks.com, priority issue response, custom check requests |

## License

MIT