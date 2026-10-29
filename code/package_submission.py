#!/usr/bin/env python3
"""
Packaging script for HackerRank Orchestrate: Ghost Data Still Exists.
Packages the runnable solution into code.zip using a strict allowlist.
Strictly excludes dataset/, .venv/, __pycache__/, log.txt, and credentials.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "code.zip"

ALLOWLIST = [
    "README.md",
    "code/main.py",
    "code/build_output.py",
    "code/validate_output.py",
    "code/package_submission.py",
    "code/validate_inventory.py",
    "code/inspect_structured_evidence.py",
    "code/inspect_unstructured_evidence.py",
    "code/tools",
    "code/tests",
    "code/evaluation",
    "code/docs",
    "evaluation/evaluation_report.md",
    "evaluation/usage_report.md",
]

EXCLUDED_PARTS = {"dataset", ".venv", "__pycache__", "node_modules"}
EXCLUDED_NAMES = {".env", ".env.local", "log.txt", "code.zip"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def candidates():
    found = set()
    for item in ALLOWLIST:
        path = ROOT / item
        if path.is_file():
            found.add(path)
        elif path.is_dir():
            found.update(p for p in path.rglob("*") if p.is_file())
        else:
            print(f"WARNING: allowlist entry absent: {item}")
    for path in sorted(found):
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in {".pyc", ".pyo"}:
            continue
        if path == ARCHIVE:
            continue
        if any(secret in path.name.casefold() for secret in ("credential", "secret", "token")):
            raise RuntimeError(f"Potential secret file in package allowlist: {rel}")
        yield path


def main() -> None:
    files = list(candidates())
    if not files:
        raise RuntimeError("Package allowlist resolved to zero files")

    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())

    with ZipFile(ARCHIVE, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        names = set(zf.namelist())
        for required in (
            "README.md",
            "code/main.py",
            "code/validate_output.py",
            "code/evaluation/main.py",
            "evaluation/evaluation_report.md",
            "evaluation/usage_report.md",
        ):
            if required not in names:
                raise RuntimeError(f"Missing required ZIP entry: {required}")
        for name in names:
            if name.startswith("dataset/") or ".venv/" in name or "__pycache__/" in name:
                raise RuntimeError(f"Forbidden entry in ZIP: {name}")
        print(f"ZIP_OK entries={len(names)} archive_sha256={sha256(ARCHIVE)}")

    out = ROOT / "output.csv"
    if out.exists():
        print(f"output_sha256={sha256(out)}")


if __name__ == "__main__":
    main()
