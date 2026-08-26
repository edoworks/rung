#!/usr/bin/env python3
"""Build and validate the complete local Rung release artifact set."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
GENERATED_NAMES = {
    "checksums.txt",
    "packages",
    "packages-a",
    "packages-b",
    "release-notes.md",
    "rung-cli.py",
    "sbom.cdx.json",
}


def run(*command: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=True, text=True, env=env)


def remove_within(path: Path, dist: Path) -> None:
    if not path.is_relative_to(dist):
        raise RuntimeError(f"refusing to remove outside dist: {path}")
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def prepare_dist(dist: Path) -> None:
    if dist == ROOT or not dist.is_relative_to(ROOT):
        raise RuntimeError("--dist must be a dedicated directory inside the repository")
    if not dist.exists():
        dist.mkdir(parents=True)
        return
    unexpected = sorted(
        path.name
        for path in dist.iterdir()
        if path.name not in GENERATED_NAMES and not path.name.startswith(".validate-release-")
    )
    if unexpected:
        raise RuntimeError(f"refusing to remove unknown dist content: {', '.join(unexpected)}")
    for path in list(dist.iterdir()):
        remove_within(path, dist)


def compare_trees(first: Path, second: Path) -> None:
    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    if first_files != second_files:
        raise RuntimeError("reproducible builds produced different artifact paths")
    for relative in first_files:
        if (first / relative).read_bytes() != (second / relative).read_bytes():
            raise RuntimeError(f"reproducible builds differ: {relative}")


def project_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version ="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("pyproject.toml has no project version")


def run_json(command: list[str], output: Path, environment: dict[str, str]) -> None:
    with output.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            command, cwd=ROOT, stdout=stream, text=True, env=environment
        )
    if result.returncode != 1:
        raise RuntimeError(f"quality gate returned {result.returncode}, expected 1: {' '.join(command)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    dist = args.dist.resolve()
    prepare_dist(dist)

    build_a = dist / "packages-a"
    build_b = dist / "packages-b"
    packages = dist / "packages"

    environment = os.environ.copy()
    for name in list(environment):
        if name == "PYTHONHOME" or name == "PYTHONPATH" or name.startswith("PIP_"):
            environment.pop(name)
    environment["PYTHONNOUSERSITE"] = "1"
    epoch = subprocess.check_output(
        ("git", "log", "-1", "--format=%ct"),
        cwd=ROOT,
        text=True,
        env=environment,
    ).strip()
    if not epoch.isdecimal():
        raise RuntimeError("Git did not provide a numeric SOURCE_DATE_EPOCH")
    environment["SOURCE_DATE_EPOCH"] = epoch
    for output in (build_a, build_b):
        run(sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output), env=environment)
        run(sys.executable, "scripts/normalize_sdist.py", "--dist", str(output), env=environment)
    compare_trees(build_a, build_b)
    shutil.move(str(build_a), str(packages))
    remove_within(build_b, dist)

    run(
        sys.executable,
        "scripts/build_single_file.py",
        "--output",
        str(dist / "rung-cli.py"),
        env=environment,
    )
    notes = ROOT / "docs" / "releases" / f"v{project_version()}.md"
    if not notes.is_file():
        raise RuntimeError(f"version-matched release notes are missing: {notes}")
    shutil.copyfile(notes, dist / "release-notes.md")
    run(sys.executable, "scripts/release_artifacts.py", "--dist", str(dist), env=environment)

    temporary = Path(tempfile.mkdtemp(prefix=".validate-release-", dir=dist))
    try:
        venv = temporary / "venv"
        run(sys.executable, "-m", "venv", str(venv), env=environment)
        venv_python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        wheels = sorted(packages.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("expected exactly one built wheel")
        install_environment = environment.copy()
        install_environment["PIP_CONFIG_FILE"] = os.devnull
        install_environment["PIP_NO_INDEX"] = "1"
        run(
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            str(wheels[0]),
            env=install_environment,
        )
        wheel_cli = venv / ("Scripts/rung.exe" if os.name == "nt" else "bin/rung")
        if not wheel_cli.is_file():
            raise RuntimeError("wheel did not install the rung command")
        fixture = ROOT / "tests" / "fixtures" / "excellent_public_evidence"
        run_json(
            [str(wheel_cli), "--root", str(fixture), "--json"],
            temporary / "wheel.json",
            environment,
        )
        run_json(
            [sys.executable, "-m", "rung", "--root", str(fixture), "--json"],
            temporary / "modular.json",
            environment,
        )
        run_json(
            [
                sys.executable,
                str(dist / "rung-cli.py"),
                "--root",
                str(fixture),
                "--json",
            ],
            temporary / "standalone.json",
            environment,
        )
        reports = [
            json.loads((temporary / name).read_text(encoding="utf-8"))
            for name in ("wheel.json", "modular.json", "standalone.json")
        ]
        for report in reports:
            report.pop("timestamp", None)
            report.pop("report_data_sha256", None)
        if reports[0] != reports[1] or reports[1] != reports[2]:
            raise RuntimeError("wheel, modular, and standalone JSON reports differ")
    finally:
        remove_within(temporary, dist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
