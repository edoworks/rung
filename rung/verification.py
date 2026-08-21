"""Reproducible verification receipts and replay observations."""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from rung import __version__
from rung.audit import SCHEMA_VERSION as AUDIT_SCHEMA_VERSION
from rung.audit import run_audit
from rung.git_snapshot import SnapshotError, compare_worktree, load_commit, load_tree, materialize, run_git


RECEIPT_SCHEMA = "RungVerificationReceipt/v1"
OBSERVATION_SCHEMA = "RungReplayObservation/v1"
MAX_JSON_BYTES = 1_048_576
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REPOSITORY = re.compile(r"github\.com/[a-z0-9_.-]+/[a-z0-9_.-]+\Z")
RFC3339_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
GATES = {"PASS", "FAIL"}
AUTHORITIES = {
    "unsafe", "local_only", "pr_only_provisional", "owner_evidence_required",
}
LIMITATIONS = [
    "Public repository contents cannot establish unobservable hosting-platform controls.",
    "Unsigned reproducibility evidence is not attestation, certification, enforcement proof, or correctness proof.",
]
RECEIPT_FIELDS = {
    "schema_version", "repository", "commit_sha", "tree_sha", "commit_timestamp",
    "audit_result_schema", "audit_result_sha256", "quality_gate", "authority",
    "rung_version", "engine_artifact_sha256", "argv", "limitations",
    "receipt_sha256",
}
OBSERVATION_FIELDS = {
    "schema_version", "receipt_sha256", "repository", "commit_sha", "tree_sha",
    "commit_timestamp", "audit_result_schema", "audit_result_sha256",
    "quality_gate", "authority", "rung_version", "engine_artifact_sha256",
    "matched", "mismatch_categories", "observation_sha256",
}
MISMATCH_ORDER = (
    "engine", "repository", "commit", "tree", "commit_timestamp",
    "audit_schema", "audit_digest", "quality_gate", "authority",
)


class VerificationError(Exception):
    """Malformed input or a runtime condition that prevents trusted output."""


def canonical_json(value: dict) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: dict, field: str) -> str:
    return hashlib.sha256(canonical_json({k: v for k, v in value.items() if k != field})).hexdigest()


def engine_artifact_sha256() -> str:
    """Digest the generator's canonical UTF-8 bundled-source byte stream."""
    bundled = getattr(builtins, "_RUNG_BUNDLED_SOURCES", None)
    if bundled is None:
        package = Path(__file__).resolve().parent
        sources = {}
        for path in sorted(package.rglob("*.py")):
            source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            relative = path.relative_to(package.parent).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            sources[".".join(parts)] = source
    else:
        sources = bundled
    digest = hashlib.sha256()
    if not isinstance(sources, Mapping):
        raise VerificationError("invalid bundled engine source map")
    for name in sorted(sources):
        source = sources[name]
        if not isinstance(name, str) or not isinstance(source, str):
            raise VerificationError("invalid bundled engine source map")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _git(root: Path, *args: str, max_bytes: int = 262_144) -> str:
    try:
        output = run_git(root, tuple(args), max_bytes)
    except SnapshotError as exc:
        raise VerificationError(str(exc)) from exc
    try:
        return output.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise VerificationError("git returned non-UTF-8 metadata") from exc


def normalize_repository(remote: str) -> str:
    remote = remote.strip()
    if remote.startswith("git@github.com:"):
        path = remote[len("git@github.com:"):]
    elif remote.startswith("ssh://") or remote.startswith("https://"):
        parsed = urlparse(remote)
        if (parsed.hostname or "").lower() != "github.com":
            raise VerificationError("origin must be hosted on github.com")
        if parsed.port is not None or parsed.query or parsed.fragment:
            raise VerificationError("unsupported GitHub origin URL")
        if parsed.scheme == "https" and (parsed.username is not None or parsed.password is not None):
            raise VerificationError("credential-bearing GitHub origin is unsupported")
        if parsed.scheme == "ssh" and parsed.username not in (None, "git"):
            raise VerificationError("unsupported GitHub SSH origin")
        path = parsed.path.lstrip("/")
    else:
        raise VerificationError("missing or unsupported origin URL")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise VerificationError("origin must identify one GitHub owner/repository")
    return "github.com/" + "/".join(part.lower() for part in parts)


def _assert_engine_outside(root: Path) -> None:
    if getattr(builtins, "_RUNG_BUNDLED_SOURCES", None) is not None:
        engine_path = Path(sys.argv[0]).resolve(strict=True)
    else:
        engine_path = Path(__file__).resolve(strict=True).parent
    if engine_path.is_relative_to(root):
        raise VerificationError("Rung must be independently installed outside the audited checkout")


def inspect_checkout(root_value: str | Path) -> dict:
    root = Path(root_value).resolve(strict=True)
    if not root.is_dir():
        raise VerificationError("root is not a directory")
    top = Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top != root:
        raise VerificationError("root must be the Git checkout root")
    if _git(
        root, "status", "--porcelain=v1", "--untracked-files=all",
        "--ignored=matching", "--ignore-submodules=all",
    ):
        raise VerificationError("checkout must be clean, including untracked files")
    _assert_engine_outside(root)
    commit = _git(root, "rev-parse", "--verify", "HEAD")
    if not HEX40.fullmatch(commit):
        raise VerificationError("Git returned a noncanonical object identity")
    repository = normalize_repository(_git(root, "remote", "get-url", "origin"))
    try:
        tree, committer_epoch = load_commit(root, commit)
        timestamp = datetime.fromtimestamp(
            committer_epoch, timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = load_tree(root, tree)
        compare_worktree(root, snapshot)
    except SnapshotError as exc:
        raise VerificationError(str(exc)) from exc
    return {
        "root": root, "repository": repository, "commit_sha": commit,
        "tree_sha": tree, "commit_timestamp": timestamp, "snapshot": snapshot,
    }


def _validate_output(path_value: str | Path, root: Path) -> tuple[Path, Path, tuple[int, int]]:
    path = Path(path_value).absolute()
    supplied_parent = path.parent
    try:
        parent = supplied_parent.resolve(strict=True)
    except OSError as exc:
        raise VerificationError("output parent must already exist") from exc
    if not parent.is_dir() or supplied_parent.is_symlink():
        raise VerificationError("unsafe output parent")
    destination = parent / path.name
    if destination.is_relative_to(root):
        raise VerificationError("output destination must be outside checkout")
    if destination.exists() or destination.is_symlink():
        raise VerificationError("output destination already exists")
    metadata = parent.stat(follow_symlinks=False)
    return destination, parent, (metadata.st_dev, metadata.st_ino)


def _open_validated_parent(parent: Path, expected: tuple[int, int]) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(parent.anchor, flags)
    try:
        for component in parent.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) != expected:
            raise VerificationError("output parent changed during validation")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _write_exclusive(path_value: str | Path, root: Path, value: dict) -> None:
    path, parent, parent_identity = _validate_output(path_value, root)
    data = canonical_json(value)
    descriptor = None
    directory_fd = None
    temporary = f".rung-{secrets.token_hex(16)}"
    try:
        directory_fd = _open_validated_parent(parent, parent_identity)
        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, file_flags, 0o600, dir_fd=directory_fd)
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written == 0:
                raise OSError("short write")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(
            temporary, path.name, src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd, follow_symlinks=False,
        )
        os.unlink(temporary, dir_fd=directory_fd)
        temporary = ""
        os.fsync(directory_fd)
    except FileExistsError as exc:
        raise VerificationError("output destination already exists") from exc
    except OSError as exc:
        raise VerificationError(f"cannot safely create output: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary and directory_fd is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass
        if directory_fd is not None:
            os.close(directory_fd)


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise VerificationError(f"duplicate JSON member: {key}")
        value[key] = item
    return value


def _load_json(path_value: str | Path) -> dict:
    path = Path(path_value)
    descriptor = None
    try:
        if path.is_symlink() or not path.is_file():
            raise VerificationError("receipt must be a regular non-symlink file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise VerificationError("receipt must be a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(MAX_JSON_BYTES + 1)
    except OSError as exc:
        raise VerificationError(f"cannot read receipt: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(data) > MAX_JSON_BYTES:
        raise VerificationError("receipt exceeds size limit")
    try:
        text = data.decode("utf-8", "strict")
        value = json.loads(text, object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("receipt is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise VerificationError("receipt must be a JSON object")
    return value


def validate_receipt(value: dict) -> None:
    if set(value) != RECEIPT_FIELDS:
        raise VerificationError("receipt has missing or unknown fields")
    string_fields = RECEIPT_FIELDS - {"argv", "limitations"}
    if any(not isinstance(value[field], str) for field in string_fields):
        raise VerificationError("receipt string field has invalid type")
    if value["schema_version"] != RECEIPT_SCHEMA:
        raise VerificationError("unsupported receipt schema")
    if not REPOSITORY.fullmatch(value["repository"]):
        raise VerificationError("invalid repository identity")
    for field in ("commit_sha", "tree_sha"):
        if not HEX40.fullmatch(value[field]):
            raise VerificationError(f"invalid {field}")
    for field in ("audit_result_sha256", "engine_artifact_sha256", "receipt_sha256"):
        if not HEX64.fullmatch(value[field]):
            raise VerificationError(f"invalid {field}")
    if not VERSION.fullmatch(value["audit_result_schema"]) or not VERSION.fullmatch(value["rung_version"]):
        raise VerificationError("invalid component version")
    if value["quality_gate"] not in GATES or value["authority"] not in AUTHORITIES:
        raise VerificationError("invalid gate or authority")
    if not RFC3339_UTC.fullmatch(value["commit_timestamp"]):
        raise VerificationError("invalid commit timestamp")
    expected_argv = [
        "rung", "--root", "{checkout}", "--commit-sha", value["commit_sha"],
        "--repository", value["repository"], "--timestamp",
        value["commit_timestamp"], "--json",
    ]
    if value["argv"] != expected_argv or value["limitations"] != LIMITATIONS:
        raise VerificationError("noncanonical receipt metadata")
    if value["receipt_sha256"] != _digest(value, "receipt_sha256"):
        raise VerificationError("receipt self-digest mismatch")


def _audit(identity: dict):
    try:
        with materialize(identity["snapshot"]) as immutable_root:
            return run_audit(
                immutable_root, commit_sha=identity["commit_sha"],
                repository=identity["repository"], timestamp=identity["commit_timestamp"],
            )
    except SnapshotError as exc:
        raise VerificationError(str(exc)) from exc


def _confirm_unchanged(identity: dict) -> None:
    current = inspect_checkout(identity["root"])
    for field in ("repository", "commit_sha", "tree_sha", "commit_timestamp"):
        if current[field] != identity[field]:
            raise VerificationError("checkout changed during audit")


def create_receipt(root_value: str | Path, output: str | Path) -> dict:
    identity = inspect_checkout(root_value)
    result = _audit(identity)
    _confirm_unchanged(identity)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "repository": identity["repository"],
        "commit_sha": identity["commit_sha"],
        "tree_sha": identity["tree_sha"],
        "commit_timestamp": identity["commit_timestamp"],
        "audit_result_schema": result.schema_version,
        "audit_result_sha256": result.report_data_sha256,
        "quality_gate": result.quality_gate,
        "authority": result.authority.value,
        "rung_version": __version__,
        "engine_artifact_sha256": engine_artifact_sha256(),
        "argv": [
            "rung", "--root", "{checkout}", "--commit-sha", identity["commit_sha"],
            "--repository", identity["repository"], "--timestamp",
            identity["commit_timestamp"], "--json",
        ],
        "limitations": LIMITATIONS,
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = _digest(receipt, "receipt_sha256")
    _write_exclusive(output, identity["root"], receipt)
    return receipt


def replay_receipt(root_value: str | Path, receipt_path: str | Path, output: str | Path) -> tuple[dict, bool]:
    receipt = _load_json(receipt_path)
    validate_receipt(receipt)
    identity = inspect_checkout(root_value)
    result = _audit(identity)
    _confirm_unchanged(identity)
    observed = {
        "repository": identity["repository"], "commit_sha": identity["commit_sha"],
        "tree_sha": identity["tree_sha"], "commit_timestamp": identity["commit_timestamp"],
        "audit_result_schema": result.schema_version,
        "audit_result_sha256": result.report_data_sha256,
        "quality_gate": result.quality_gate, "authority": result.authority.value,
        "rung_version": __version__, "engine_artifact_sha256": engine_artifact_sha256(),
    }
    comparisons = {
        "engine": (receipt["rung_version"], receipt["engine_artifact_sha256"]) == (observed["rung_version"], observed["engine_artifact_sha256"]),
        "repository": receipt["repository"] == observed["repository"],
        "commit": receipt["commit_sha"] == observed["commit_sha"],
        "tree": receipt["tree_sha"] == observed["tree_sha"],
        "commit_timestamp": receipt["commit_timestamp"] == observed["commit_timestamp"],
        "audit_schema": receipt["audit_result_schema"] == observed["audit_result_schema"],
        "audit_digest": receipt["audit_result_sha256"] == observed["audit_result_sha256"],
        "quality_gate": receipt["quality_gate"] == observed["quality_gate"],
        "authority": receipt["authority"] == observed["authority"],
    }
    mismatches = [category for category in MISMATCH_ORDER if not comparisons[category]]
    observation = {
        "schema_version": OBSERVATION_SCHEMA,
        "receipt_sha256": receipt["receipt_sha256"],
        **observed,
        "matched": not mismatches,
        "mismatch_categories": mismatches,
        "observation_sha256": "",
    }
    if set(observation) != OBSERVATION_FIELDS:
        raise AssertionError("observation schema implementation error")
    observation["observation_sha256"] = _digest(observation, "observation_sha256")
    _write_exclusive(output, identity["root"], observation)
    return observation, not mismatches


def verification_main(command: str, root: str, receipt: str, observation: str | None = None) -> int:
    try:
        if command == "verify":
            create_receipt(root, receipt)
            return 0
        _, matched = replay_receipt(root, receipt, observation or "")
        return 0 if matched else 2
    except VerificationError as exc:
        print(f"rung {command}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"rung {command}: runtime error: {exc}", file=sys.stderr)
        return 1
