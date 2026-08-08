#!/usr/bin/env python3
"""Regenerate the adapted-file map from the pinned upstream Git commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

from privacy_gate import WALK_IGNORES, expected_origin, load_origin_policy


OUTPUT_PATH = Path("release/upstream-map.lock.json")
UPSTREAM_SKILL_ROOT = PurePosixPath("skills/ppt-master")


def git_output(repository: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "git command failed")
    return process.stdout.strip()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def build_map(root: Path, upstream_repository: Path) -> dict[str, object]:
    root = root.resolve()
    upstream_repository = upstream_repository.resolve()
    policy = load_origin_policy(root)
    upstream = dict(policy["upstream"])
    commit = str(upstream["commit"])
    skill_root = PurePosixPath(str(policy["skill_root"]))
    skill_directory = root / skill_root

    if git_output(upstream_repository, "cat-file", "-t", commit) != "commit":
        raise RuntimeError(f"upstream object is not a commit: {commit}")

    records: dict[str, dict[str, str]] = {}
    for path in sorted(skill_directory.rglob("*")):
        if not path.is_file() or any(part in WALK_IGNORES for part in path.parts):
            continue
        repository_path = path.relative_to(root).as_posix()
        if expected_origin(repository_path, policy) != "adapted-mit-upstream":
            continue
        relative = PurePosixPath(repository_path).relative_to(skill_root)
        upstream_path = (UPSTREAM_SKILL_ROOT / relative).as_posix()
        upstream_blob = git_output(
            upstream_repository,
            "rev-parse",
            f"{commit}:{upstream_path}",
        )
        if git_output(upstream_repository, "cat-file", "-t", upstream_blob) != "blob":
            raise RuntimeError(f"upstream path is not a blob: {upstream_path}")
        local_blob = git_blob_sha1(path.read_bytes())
        records[repository_path] = {
            "upstream_path": upstream_path,
            "upstream_git_blob_sha1": upstream_blob,
            "relation": "identical" if local_blob == upstream_blob else "modified",
        }

    return {
        "schema_version": 1,
        "upstream": upstream,
        "adapted_files": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Deckestra repository root")
    parser.add_argument(
        "--upstream-repository",
        required=True,
        help="local Git clone containing the pinned hugohe3/ppt-master commit",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    payload = build_map(root, Path(args.upstream_repository))
    target = root / OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    identical = sum(
        record["relation"] == "identical"
        for record in payload["adapted_files"].values()
    )
    total = len(payload["adapted_files"])
    print(
        f"wrote {target}: {total} adapted files "
        f"({identical} identical, {total - identical} modified)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
