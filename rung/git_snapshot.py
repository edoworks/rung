"""Safe, bounded materialization of regular files from a Git tree."""

from __future__ import annotations

import hashlib
import os
import selectors
import stat
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


MAX_TREE_BYTES = 16 * 1024 * 1024
MAX_COMMIT_BYTES = 1024 * 1024
MAX_BLOB_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
GIT_TIMEOUT_SECONDS = 30
GIT_PREFIX = [
    "git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
    "-c", "protocol.ext.allow=never",
]


class SnapshotError(Exception):
    """Git metadata or content cannot produce a trusted regular-file tree."""


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    mode: str
    oid: str
    data: bytes


def run_git(root: Path, args: tuple[str, ...], max_stdout: int) -> bytes:
    """Run a non-interactive local Git command with strictly bounded pipes."""
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    try:
        process = subprocess.Popen(
            [*GIT_PREFIX, "-C", str(root), *args], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={
                **os.environ, "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
            },
        )
    except OSError as exc:
        raise SnapshotError(f"cannot run git: {exc}") from exc
    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, (stdout_buffer, max_stdout))
    selector.register(process.stderr, selectors.EVENT_READ, (stderr_buffer, MAX_STDERR_BYTES))
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SnapshotError("git command timed out")
            events = selector.select(remaining)
            if not events:
                raise SnapshotError("git command timed out")
            for key, _ in events:
                chunk = os.read(key.fd, 65_536)
                buffer, limit = key.data
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    buffer.extend(chunk)
                    if len(buffer) > limit:
                        raise SnapshotError("git output exceeds safety bound")
        returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if returncode:
        message = stderr_buffer.decode("utf-8", "replace").strip()
        raise SnapshotError(f"git command failed: {message or args[0]}")
    if stderr_buffer:
        raise SnapshotError("git emitted unexpected diagnostics")
    return bytes(stdout_buffer)


def _safe_path(raw: bytes) -> tuple[str, list[str]]:
    try:
        path = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise SnapshotError("Git tree contains a non-UTF-8 path") from exc
    parts = path.split("/")
    if not path or path.startswith("/") or "\\" in path or any(ord(char) < 32 or ord(char) == 127 for char in path) or any(
        part in ("", ".", "..") for part in parts
    ):
        raise SnapshotError("Git tree contains an unsafe path")
    return path, parts


def _validate_path(raw: bytes, files: set[str], directories: set[str]) -> str:
    path, parts = _safe_path(raw)
    if path in files or path in directories:
        raise SnapshotError("Git tree contains a duplicate or prefix path conflict")
    parents = ["/".join(parts[:index]) for index in range(1, len(parts))]
    if any(parent in files for parent in parents):
        raise SnapshotError("Git tree contains a duplicate or prefix path conflict")
    files.add(path)
    directories.update(parents)
    return path


def _validate_directory(raw: bytes, files: set[str], directories: set[str]) -> None:
    path, parts = _safe_path(raw)
    parents = ["/".join(parts[:index]) for index in range(1, len(parts))]
    if path in files or path in directories or any(parent in files for parent in parents):
        raise SnapshotError("Git tree contains a duplicate or prefix path conflict")
    directories.add(path)
    directories.update(parents)


def _verified_object(root: Path, kind: str, oid: str, limit: int) -> bytes:
    data = run_git(root, ("cat-file", kind, oid), limit)
    actual = hashlib.sha1(
        kind.encode("ascii") + b" " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()
    if actual != oid:
        raise SnapshotError(f"Git {kind} object digest mismatch")
    return data


def load_commit(root: Path, commit_oid: str) -> tuple[str, int]:
    """Read one authenticated commit object and return its tree and epoch."""
    data = _verified_object(root, "commit", commit_oid, MAX_COMMIT_BYTES)
    headers, separator, _ = data.partition(b"\n\n")
    if not separator:
        raise SnapshotError("Git returned malformed commit metadata")
    tree = None
    committer_epoch = None
    for line in headers.splitlines():
        if line.startswith(b"tree "):
            if tree is not None:
                raise SnapshotError("Git commit has duplicate tree metadata")
            candidate = line[5:]
            if len(candidate) != 40 or any(byte not in b"0123456789abcdef" for byte in candidate):
                raise SnapshotError("Git commit has invalid tree metadata")
            tree = candidate.decode("ascii")
        elif line.startswith(b"committer "):
            if committer_epoch is not None:
                raise SnapshotError("Git commit has duplicate committer metadata")
            fields = line.rsplit(b" ", 2)
            if len(fields) != 3 or not fields[1].isdigit():
                raise SnapshotError("Git commit has invalid committer metadata")
            committer_epoch = int(fields[1])
    if tree is None or committer_epoch is None:
        raise SnapshotError("Git commit is missing required metadata")
    return tree, committer_epoch


def load_tree(root: Path, tree_oid: str) -> tuple[SnapshotFile, ...]:
    files: set[str] = set()
    directories: set[str] = set()
    snapshot: list[SnapshotFile] = []
    tree_bytes = 0
    content_bytes = 0

    def visit(oid: str, prefix: bytes, depth: int) -> None:
        nonlocal tree_bytes, content_bytes
        if depth > 128:
            raise SnapshotError("Git tree nesting exceeds safety bound")
        raw = _verified_object(root, "tree", oid, MAX_TREE_BYTES)
        tree_bytes += len(raw)
        if tree_bytes > MAX_TREE_BYTES:
            raise SnapshotError("Git tree metadata exceeds safety bound")
        position = 0
        while position < len(raw):
            space = raw.find(b" ", position)
            nul = raw.find(b"\0", space + 1) if space >= 0 else -1
            if space <= position or nul <= space + 1 or nul + 21 > len(raw):
                raise SnapshotError("Git returned malformed tree metadata")
            mode = raw[position:space]
            name = raw[space + 1:nul]
            raw_oid = raw[nul + 1:nul + 21]
            position = nul + 21
            if b"/" in name:
                raise SnapshotError("Git tree contains an unsafe path")
            child_oid = raw_oid.hex()
            raw_path = prefix + name
            if mode == b"40000":
                _validate_directory(raw_path, files, directories)
                visit(child_oid, raw_path + b"/", depth + 1)
                continue
            path = _validate_path(raw_path, files, directories)
            if mode in (b"120000", b"160000"):
                kind = "symlinks" if mode == b"120000" else "submodules"
                raise SnapshotError(f"tracked {kind} are unsupported in receipt mode: {path}")
            if mode not in (b"100644", b"100755"):
                raise SnapshotError(f"unsupported Git tree entry: {path}")
            data = _verified_object(root, "blob", child_oid, MAX_BLOB_BYTES)
            content_bytes += len(data)
            if content_bytes > MAX_TOTAL_BYTES:
                raise SnapshotError("Git tree contents exceed safety bound")
            snapshot.append(SnapshotFile(path, mode.decode("ascii"), child_oid, data))

    visit(tree_oid, b"", 0)
    return tuple(snapshot)


def _open_directory(parent_fd: int, name: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(name, flags, dir_fd=parent_fd)


def compare_worktree(root: Path, snapshot: tuple[SnapshotFile, ...]) -> None:
    root_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        for entry in snapshot:
            directory_fd = os.dup(root_fd)
            descriptor = None
            try:
                parts = entry.path.split("/")
                for part in parts[:-1]:
                    next_fd = _open_directory(directory_fd, part)
                    os.close(directory_fd)
                    directory_fd = next_fd
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(parts[-1], flags, dir_fd=directory_fd)
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise SnapshotError(f"tracked path is not a regular file: {entry.path}")
                if bool(metadata.st_mode & 0o111) != (entry.mode == "100755"):
                    raise SnapshotError(f"tracked file mode differs from HEAD: {entry.path}")
                with os.fdopen(descriptor, "rb") as stream:
                    descriptor = None
                    data = stream.read(len(entry.data) + 1)
                if data != entry.data:
                    raise SnapshotError(f"tracked file content differs from HEAD: {entry.path}")
            except OSError as exc:
                raise SnapshotError(f"cannot safely read tracked file: {entry.path}") from exc
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                os.close(directory_fd)
    finally:
        os.close(root_fd)


def _write_all(descriptor: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("short write")
        remaining = remaining[written:]


@contextmanager
def materialize(snapshot: tuple[SnapshotFile, ...]) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="rung-snapshot-") as directory:
        root = Path(directory)
        root_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        created: set[str] = set()
        try:
            for entry in snapshot:
                directory_fd = os.dup(root_fd)
                descriptor = None
                try:
                    parts = entry.path.split("/")
                    current = []
                    for part in parts[:-1]:
                        current.append(part)
                        key = "/".join(current)
                        if key not in created:
                            os.mkdir(part, 0o700, dir_fd=directory_fd)
                            created.add(key)
                        next_fd = _open_directory(directory_fd, part)
                        os.close(directory_fd)
                        directory_fd = next_fd
                    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                    descriptor = os.open(parts[-1], flags, 0o700 if entry.mode == "100755" else 0o600, dir_fd=directory_fd)
                    _write_all(descriptor, entry.data)
                    os.close(descriptor)
                    descriptor = None
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
                    os.close(directory_fd)
        except OSError as exc:
            raise SnapshotError(f"cannot safely materialize Git tree: {exc}") from exc
        finally:
            os.close(root_fd)
        yield root
