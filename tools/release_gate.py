#!/usr/bin/env python3
"""Run Deckestra's read-only source-release checks from one entry point."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


IGNORED_DIRECTORIES = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}
)


class ReleaseGateError(RuntimeError):
    """Raised when a release check cannot complete successfully."""


def iter_source_files(root: Path, suffixes: set[str]) -> Iterable[Path]:
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRECTORIES)
        current_path = Path(current)
        for name in sorted(files):
            path = current_path / name
            if path.suffix.lower() in suffixes:
                yield path


def validate_json(root: Path) -> int:
    count = 0
    for path in iter_source_files(root, {".json"}):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            relative = path.relative_to(root).as_posix()
            raise ReleaseGateError(f"invalid JSON: {relative}: {exc}") from exc
        count += 1
    if not count:
        raise ReleaseGateError("no JSON documents found")
    print(f"[PASS] JSON syntax: {count} files")
    return count


def validate_python(root: Path) -> int:
    count = 0
    for path in iter_source_files(root, {".py"}):
        relative = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise ReleaseGateError(f"invalid Python: {relative}: {exc}") from exc
        count += 1
    if not count:
        raise ReleaseGateError("no Python sources found")
    print(f"[PASS] Python syntax: {count} files")
    return count


def run_command(label: str, command: list[str], root: Path) -> None:
    print(f"[RUN] {label}", flush=True)
    environment = os.environ.copy()
    environment.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    process = subprocess.run(
        command,
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if process.returncode:
        raise ReleaseGateError(f"{label} failed with exit code {process.returncode}")


def run(
    root: Path,
    *,
    history: bool = False,
    require_provenance: bool = False,
    skip_near_duplicates: bool = False,
) -> None:
    root = root.resolve()
    if not root.is_dir():
        raise ReleaseGateError(f"not a directory: {root}")

    python = sys.executable
    privacy = [python, "tools/privacy_gate.py", str(root)]
    if history:
        privacy.append("--history")
    if require_provenance:
        privacy.append("--require-provenance")
    run_command("privacy and provenance", privacy, root)

    run_command("third-party licenses", [python, "tools/license_gate.py", str(root)], root)
    run_command(
        "Skill identity and attribution",
        [python, "skills/build-editable-decks/scripts/attribution_guard.py"],
        root,
    )
    validate_json(root)
    validate_python(root)
    run_command(
        "unit and integration tests",
        [python, "-m", "unittest", "discover", "-s", "tests", "-v"],
        root,
    )
    prompt = [
        python,
        "skills/build-editable-decks/scripts/prompt_audit.py",
        "--root",
        str(root),
    ]
    if skip_near_duplicates:
        prompt.append("--skip-near-duplicates")
    run_command("prompt budget and governance", prompt, root)
    print("[PASS] Deckestra release gate")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--history", action="store_true", help="scan every reachable Git blob")
    parser.add_argument(
        "--require-provenance",
        action="store_true",
        help="require the frozen file provenance lock",
    )
    parser.add_argument(
        "--skip-near-duplicates",
        action="store_true",
        help="development-only speedup; do not use for a release build",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(
            Path(args.root),
            history=args.history,
            require_provenance=args.require_provenance,
            skip_near_duplicates=args.skip_near_duplicates,
        )
    except ReleaseGateError as exc:
        print(f"[FAIL] release gate: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
