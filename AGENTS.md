# Rung — Agent Map

Rung is an open-source CLI that audits repositories for AI agent governance readiness.

## Build & Test

```bash
python3 rung-cli.py --root .
```

## Code Style

- Python 3.10+ (dataclasses, type hints)
- No external dependencies (stdlib only)
- MIT-licensed

## Security

- Never transmit repository contents to external services
- Never execute arbitrary code from the repository being audited
- Never weaken check thresholds to make a check pass

## Testing

The CLI is validated against real repositories:
- openai/codex (AGENTS.md exemplar)
- apache/airflow (attribution + boundaries exemplar)
- danshapiro/trycycle (agent skill with AGENTS.md)
- strongdm/comply (SOC2 compliance tool)