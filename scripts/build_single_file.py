#!/usr/bin/env python3
"""Build the deterministic standalone Rung CLI from the modular package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "rung"
DEFAULT_OUTPUT = ROOT / "rung-cli.py"


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def render() -> str:
    sources = {}
    digest = hashlib.sha256()
    for path in sorted(PACKAGE.rglob("*.py")):
        source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        name = module_name(path)
        sources[name] = source
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(source.encode())
        digest.update(b"\0")

    payload = json.dumps(sources, sort_keys=True, separators=(",", ":"))
    return f'''#!/usr/bin/env python3
"""Generated standalone Rung CLI. Do not edit; run scripts/build_single_file.py."""

# source-sha256: {digest.hexdigest()}
import importlib.abc
import importlib.util

_SOURCES = {payload}


class _BundledLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in _SOURCES:
            return None
        is_package = fullname == "rung" or any(
            name.startswith(fullname + ".") for name in _SOURCES
        )
        return importlib.util.spec_from_loader(fullname, self, is_package=is_package)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = "<rung-single-file>/" + module.__name__.replace(".", "/") + ".py"
        exec(compile(_SOURCES[module.__name__], module.__file__, "exec"), module.__dict__)


import sys
sys.meta_path.insert(0, _BundledLoader())

from rung.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
            print(f"stale generated artifact: {args.output}")
            return 1
        return 0
    args.output.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
