"""Cross-platform tests for bounded Git subprocess output."""

from __future__ import annotations

import tempfile
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from rung.git_snapshot import SnapshotError, run_git


class GitSnapshotTest(unittest.TestCase):
    def test_run_git_reads_stdout_and_enforces_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run_git(root, ("--version",), 1024).split()[0], b"git")
            with self.assertRaisesRegex(SnapshotError, "output exceeds safety bound"):
                run_git(root, ("--version",), 1)

    def test_run_git_does_not_wait_forever_for_inherited_pipe_handles(self):
        child = "import time; time.sleep(0.3)"
        parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as directory, patch(
            "rung.git_snapshot.GIT_PREFIX", [sys.executable, "-c", parent]
        ), patch("rung.git_snapshot.PIPE_DRAIN_SECONDS", 0.02):
            with self.assertRaisesRegex(SnapshotError, "output pipes did not close"):
                run_git(Path(directory), (), 1024)
        self.assertLess(time.monotonic() - started, 1.0)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and any(
            thread.name.startswith("rung-git-") for thread in threading.enumerate()
        ):
            time.sleep(0.01)
        self.assertFalse(any(
            thread.name.startswith("rung-git-") for thread in threading.enumerate()
        ))


if __name__ == "__main__":
    unittest.main()
