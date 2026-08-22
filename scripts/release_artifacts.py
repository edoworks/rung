#!/usr/bin/env python3
"""Generate deterministic checksum and minimal CycloneDX metadata for dist/ artifacts."""

from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    dist = args.dist.resolve()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = next(line.split("=", 1)[1].strip().strip('"') for line in pyproject.splitlines() if line.startswith("version ="))
    artifacts = sorted(path for path in dist.rglob("*") if path.is_file() and path.name not in {"checksums.txt", "sbom.cdx.json"})
    if not artifacts:
        raise SystemExit("dist/ contains no release artifacts")
    checksums = "".join(f"{sha256(path)}  {path.relative_to(dist)}\n" for path in artifacts)
    (dist / "checksums.txt").write_text(checksums, encoding="utf-8")
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "rung-audit", "version": version, "licenses": [{"license": {"id": "MIT"}}]}},
        "components": [{"type": "file", "name": str(path.relative_to(dist)), "hashes": [{"alg": "SHA-256", "content": sha256(path)}]} for path in artifacts],
    }
    (dist / "sbom.cdx.json").write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
