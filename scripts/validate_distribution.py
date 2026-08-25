#!/usr/bin/env python3
"""Validate Rung's factual distribution contract without external access."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    manifest = json.loads(read(ROOT / "product-manifest.json"))
    assert manifest["schema"] == "foculoom-product/v0.1"
    assert manifest["owner"] == "Foculoom LLC"
    assert manifest["builder"] == "Edoworks"
    assert manifest["evidence"]["external_adoption"] == "unverified"
    assert manifest["evidence"]["benchmark"] == "pending"

    pyproject = read(ROOT / "pyproject.toml")
    for required in (
        'description = "Assess observable repository evidence for responsible AI coding-agent authority"',
        'readme = "README.md"',
        'Homepage = "https://rung.edoworks.com/"',
        'Repository = "https://github.com/edoworks/rung"',
        'Issues = "https://github.com/edoworks/rung/issues"',
        'Changelog = "https://github.com/edoworks/rung/releases"',
    ):
        assert required in pyproject

    channels = {channel["id"]: channel for channel in manifest["channels"]}
    assert channels["website"]["status"] == "available"
    for channel in ("github-release", "pypi", "github-actions"):
        assert channels[channel]["status"] == "planned"

    action = read(ROOT / "action.yml")
    for name in ("root", "minimum-score", "require-gate", "output-format", "report-path"):
        assert f"  {name}:" in action
    for name in ("score", "grade", "quality-gate", "recommended-authority", "report-path"):
        assert f"  {name}:" in action
    assert "contents: write" not in action
    assert "pulls: write" not in action
    assert "rung-cli.py" in action
    assert "relative_to(workspace)" in action
    assert "root must not contain symlinks" in action
    assert "contains a control character" in action

    skill = read(ROOT / "skills" / "rung-reproducible-verification" / "SKILL.md")
    assert skill.startswith("---\nname: rung-reproducible-verification\n")
    assert "independently installed, version-pinned `rung`" in skill
    assert "must not be rewritten to appear successful" in " ".join(skill.split())

    workflow = read(ROOT / ".github" / "workflows" / "release.yml")
    for required in ("python -m build", "pip install", "rung-cli.py", "release_artifacts.py", "attest-build-provenance", "id-token: write", "tag version does not match pyproject.toml"):
        assert required in workflow
    assert "pypa/gh-action-pypi-publish" in workflow
    assert "--require-hashes -r requirements-release.txt" in workflow
    assert "python -m build --no-isolation" in workflow
    assert "SOURCE_DATE_EPOCH" in workflow
    assert "diff -r dist/packages-a dist/packages-b" in workflow
    assert "normalize_sdist.py --dist dist/packages-a" in workflow
    assert "password:" not in workflow
    for mutable in ("@v4", "@v5", "@v2", "@release/v1"):
        assert mutable not in workflow
    assert "github-release:" in workflow and "  attest:" in workflow
    assert "release tag must bind the exact current origin/main revision" in workflow
    assert "release tag must be strict vMAJOR.MINOR.PATCH" in workflow
    assert "group: release" in workflow
    assert "name: release" in workflow
    assert "body_path: dist/release-notes.md" in workflow
    assert "fail_on_unmatched_files: true" in workflow
    assert "remote release tag moved after build" in workflow
    assert "reviewed main moved after release build" in workflow
    assert "release tag must be annotated" in workflow
    release_notes = read(ROOT / "docs" / "releases" / "v0.3.0.md")
    assert "public repository evidence" in release_notes
    assert "not certification" in release_notes
    assert "paid report is not launched" in release_notes
    assert "does not establish that any registry or release channel completed publication" in " ".join(release_notes.split())
    print("Rung distribution contract validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
