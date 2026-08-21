# Agent Map

## Build & Test
python3 -m pytest

## Verification Gate
Never commit or merge before verification (pytest) passes.

## Independent Review
Before committing: complete self-review, then independent (rubberduck) review, then rerun verification, then commit.

## Agent Attribution
Generated-by: <Agent Name and Version>

## Cyclic Verification
plan -> build -> verify -> (if fail) fix -> verify again -> review

## Security Never-Rules
Never commit secrets, API keys, or credentials.
Never expose the Docker socket to construction agents.
Never use destructive git operations without explicit request.
Never weaken security policy to make a check pass.
Never skip the verification gate before commit.