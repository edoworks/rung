#!/usr/bin/env python3
"""Synchronize the skills.sh mirror from the canonical project skill."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / ".agents" / "skills" / "rung-reproducible-verification" / "SKILL.md"
MIRROR = ROOT / "skills" / "rung-reproducible-verification" / "SKILL.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    canonical = CANONICAL.read_bytes()
    if args.check:
        if MIRROR.read_bytes() != canonical:
            raise SystemExit("skills mirror differs from canonical .agents skill; run scripts/sync_skill.py")
        return 0
    MIRROR.write_bytes(canonical)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
