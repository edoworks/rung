#!/usr/bin/env python3
"""Normalize gzip wrappers around already-built source distributions."""

from __future__ import annotations

import argparse
import gzip
import io
from pathlib import Path
import tarfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    for archive in args.dist.glob("*.tar.gz"):
        source = tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive.read_bytes())), mode="r:")
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w", format=tarfile.USTAR_FORMAT) as normalized_tar:
            for member in sorted(source.getmembers(), key=lambda item: item.name):
                if not (member.isfile() or member.isdir()):
                    raise SystemExit(f"unsupported source-distribution member {member.name}")
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                normalized_tar.addfile(member, source.extractfile(member) if member.isfile() else None)
        with archive.open("wb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as normalized:
                normalized.write(payload.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
