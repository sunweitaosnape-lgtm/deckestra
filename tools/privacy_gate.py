#!/usr/bin/env python3
"""Fail closed when a release tree can contain private or user-supplied data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


SCHEMA_VERSION = 1
MAX_SOURCE_BYTES = 2 * 1024 * 1024
PROVENANCE_PATH = PurePosixPath("release/provenance.lock.json")
ORIGIN_POLICY_PATH = PurePosixPath("release/origin-policy.json")
UPSTREAM_MAP_PATH = PurePosixPath("release/upstream-map.lock.json")
ORIGIN_VALUES = frozenset(
    {"project-original", "adapted-mit-upstream", "third-party-licensed"}
)

FORBIDDEN_SUFFIXES = frozenset(
    {
        ".7z",
        ".aac",
        ".avi",
        ".bmp",
        ".csv",
        ".db",
        ".doc",
        ".docm",
        ".docx",
        ".flac",
        ".gif",
        ".heic",
        ".jpeg",
        ".jpg",
        ".key",
        ".m4a",
        ".mov",
        ".mp3",
        ".mp4",
        ".ods",
        ".odt",
        ".ogg",
        ".pdf",
        ".pem",
        ".png",
        ".ppt",
        ".pptm",
        ".pptx",
        ".psd",
        ".rar",
        ".sqlite",
        ".tar",
        ".tif",
        ".tiff",
        ".ttf",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xls",
        ".xlsm",
        ".xlsx",
        ".zip",
    }
)

FORBIDDEN_PATH_PARTS = frozenset(
    {
        ".cache",
        ".deckestra",
        ".pytest_cache",
        ".venv",
        "artifacts",
        "blind-cases",
        "cache",
        "case-data",
        "certification-runs",
        "downloads",
        "examples",
        "fixtures-private",
        "outputs",
        "projects",
        "private-cases",
        "runtime",
        "sources",
        "uploads",
        "user-data",
        "validation-runs",
    }
)

WALK_IGNORES = frozenset({".git", ".mypy_cache", ".ruff_cache", "__pycache__", "node_modules"})

MAGIC_SIGNATURES = (
    ("png", b"\x89PNG\r\n\x1a\n"),
    ("jpeg", b"\xff\xd8\xff"),
    ("gif", b"GIF8"),
    ("pdf", b"%PDF-"),
    ("zip-or-ooxml", b"PK\x03\x04"),
    ("7z", b"7z\xbc\xaf\x27\x1c"),
    ("rar", b"Rar!\x1a\x07"),
    ("sqlite", b"SQLite format 3\x00"),
    ("ole-compound-document", bytes.fromhex("d0cf11e0a1b11ae1")),
)

TRANSPARENT_PIXEL_PAYLOAD = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("openai-style-token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "assigned-secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b"
            r"\s*[:=]\s*['\"](?!example|placeholder|changeme|your[_-])[A-Za-z0-9_./+=-]{16,}['\"]"
        ),
    ),
)

DATA_IMAGE_RE = re.compile(
    r"data:image/(?:png|jpe?g|gif|webp|bmp|tiff?);base64,([A-Za-z0-9+/=]{64,})",
    re.IGNORECASE,
)

LOCAL_PATH_PATTERNS = (
    ("workspace-path", re.compile(r"/(?:workspace|private|var/folders)/[^\s'\"<>]+")),
    ("home-path", re.compile(r"/(?:home|Users)/[^\s'\"<>]+")),
    ("windows-profile-path", re.compile(r"[A-Za-z]:\\Users\\[^\s'\"<>]+", re.IGNORECASE)),
)

PRIVATE_SERVICE_TERMS = (
    "oai" + "usercontent",
    "library" + "_file_id",
    "sandbox" + ":/",
)

# Captured PowerPoint behavior-tree registry excluded from the public release.
# Hashing bytes rather than a path or Git object id also catches renames and
# repositories using a different Git object format.
FORBIDDEN_HISTORY_SHA256 = frozenset(
    {"ddf7b0a0065d17e8acfe8eee021f13771b67d649d4ba9bf8d5eeeb59c5d15e4e"}
)


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    detail: str
    source: str = "worktree"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_name(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_worktree_entries(root: Path) -> Iterable[tuple[str, os.stat_result, bytes | None]]:
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in WALK_IGNORES)
        current_path = Path(current)
        for name in sorted(files):
            path = current_path / name
            rel = relative_name(root, path)
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                yield rel, info, None
                continue
            if not stat.S_ISREG(info.st_mode):
                yield rel, info, None
                continue
            yield rel, info, path.read_bytes()


def scan_blob(path: str, data: bytes, *, source: str) -> list[Issue]:
    issues: list[Issue] = []
    pure = PurePosixPath(path)
    lowered_parts = {part.lower() for part in pure.parts}
    suffix = pure.suffix.lower()

    blocked_parts = sorted(lowered_parts & FORBIDDEN_PATH_PARTS)
    if blocked_parts:
        issues.append(Issue("forbidden-path", path, ", ".join(blocked_parts), source))
    if pure.parts and pure.parts[0].lower() == "certification":
        private_certification_parts = {
            "cases", "evidence", "reviews", "renders", "runs", "suite-data"
        }
        certification_hits = sorted(lowered_parts & private_certification_parts)
        if certification_hits or pure.name.lower() in {
            "evidence.json", "review-receipts.json", "suite-manifest.json"
        }:
            issues.append(
                Issue(
                    "private-certification-artifact",
                    path,
                    "blind-suite evidence belongs outside the repository",
                    source,
                )
            )
    if suffix in FORBIDDEN_SUFFIXES:
        issues.append(Issue("forbidden-file-type", path, suffix, source))
    if len(data) > MAX_SOURCE_BYTES:
        issues.append(Issue("oversized-source-file", path, f"{len(data)} bytes", source))

    for kind, signature in MAGIC_SIGNATURES:
        if data.startswith(signature):
            issues.append(Issue("binary-signature", path, kind, source))
            break

    if b"\x00" in data:
        issues.append(Issue("binary-content", path, "NUL byte detected", source))
        return issues

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(Issue("non-utf8-content", path, str(exc), source))
        return issues

    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append(Issue("secret-pattern", path, label, source))

    for label, pattern in LOCAL_PATH_PATTERNS:
        match = pattern.search(text)
        if match:
            issues.append(Issue("local-path", path, f"{label}: {match.group(0)[:120]}", source))

    lowered = text.lower()
    for term in PRIVATE_SERVICE_TERMS:
        if term.lower() in lowered:
            issues.append(Issue("private-service-reference", path, term, source))

    for match in DATA_IMAGE_RE.finditer(text):
        payload = match.group(1)
        if suffix == ".svg" and payload == TRANSPARENT_PIXEL_PAYLOAD:
            continue
        issues.append(
            Issue(
                "embedded-raster-image",
                path,
                f"base64 payload sha256={sha256_bytes(payload.encode('ascii'))}",
                source,
            )
        )

    if re.search(r"(?i)https?://[^\s'\"]*(?:token|signature|sig|auth|key)=", text):
        issues.append(Issue("credential-bearing-url", path, "credential-like URL query", source))

    return issues


def scan_worktree(root: Path) -> tuple[list[Issue], dict[str, str]]:
    issues: list[Issue] = []
    hashes: dict[str, str] = {}
    for rel, info, data in iter_worktree_entries(root):
        if stat.S_ISLNK(info.st_mode):
            issues.append(Issue("symlink", rel, "symbolic links are not publishable"))
            continue
        if not stat.S_ISREG(info.st_mode):
            issues.append(Issue("special-file", rel, "only regular files are publishable"))
            continue
        assert data is not None
        digest = sha256_bytes(data)
        hashes[rel] = digest
        if digest in FORBIDDEN_HISTORY_SHA256:
            issues.append(
                Issue(
                    "unreviewed-generated-data",
                    rel,
                    f"excluded generated-data sha256={digest}",
                )
            )
        issues.extend(scan_blob(rel, data, source="worktree"))
    return issues, hashes


def git_output(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return process.stdout


def scan_history(root: Path) -> list[Issue]:
    try:
        raw = git_output(root, "rev-list", "--objects", "--all")
    except RuntimeError as exc:
        if "not a git repository" in str(exc).lower():
            return [Issue("history-unavailable", ".", "repository history is required", "history")]
        raise

    objects: dict[str, set[str]] = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        oid, separator, path = line.partition(" ")
        if separator and path:
            objects.setdefault(oid, set()).add(path)

    issues: list[Issue] = []
    for oid, paths in sorted(objects.items()):
        object_type = git_output(root, "cat-file", "-t", oid).strip()
        if object_type != b"blob":
            continue
        data = git_output(root, "cat-file", "blob", oid)
        digest = sha256_bytes(data)
        if digest in FORBIDDEN_HISTORY_SHA256:
            issues.append(
                Issue(
                    "history-unreviewed-generated-data",
                    sorted(paths)[0],
                    f"excluded generated-data sha256={digest}",
                    source=f"history:{oid[:12]}",
                )
            )
        for path in sorted(paths):
            issues.extend(scan_blob(path, data, source=f"history:{oid[:12]}"))
    return issues


def load_provenance(root: Path) -> dict[str, object]:
    path = root / PROVENANCE_PATH
    if not path.is_file():
        raise ValueError(f"missing {PROVENANCE_PATH.as_posix()}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported provenance schema")
    if not isinstance(payload.get("files"), dict):
        raise ValueError("provenance files must be an object")
    return payload


def _safe_locked_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and path.as_posix() == value


def _skill_roster_sha256(root: Path, skill_root: PurePosixPath) -> str:
    base = root / skill_root
    paths: list[str] = []
    if base.is_dir():
        for path in base.rglob("*"):
            if not path.is_file() or any(part in WALK_IGNORES for part in path.parts):
                continue
            paths.append(path.relative_to(base).as_posix())
    return sha256_bytes("".join(f"{path}\n" for path in sorted(paths)).encode("utf-8"))


def load_origin_policy(root: Path) -> dict[str, object]:
    path = root / ORIGIN_POLICY_PATH
    if not path.is_file():
        raise ValueError(f"missing {ORIGIN_POLICY_PATH.as_posix()}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "skill_root",
        "skill_path_roster_sha256",
        "upstream",
        "project_original_skill_paths",
        "third_party_paths",
    }:
        raise ValueError("origin policy has an invalid field set")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported origin policy schema")
    skill_root_text = payload.get("skill_root")
    if not _safe_locked_path(skill_root_text):
        raise ValueError("origin policy skill_root is invalid")
    skill_root = PurePosixPath(skill_root_text)
    upstream = payload.get("upstream")
    if upstream != {
        "name": "hugohe3/ppt-master",
        "commit": "bbb323f0ebd6a6a230dd6063209326b53bfd2e1d",
        "license": "MIT",
    }:
        raise ValueError("origin policy upstream identity changed")
    project_paths = payload.get("project_original_skill_paths")
    third_party_paths = payload.get("third_party_paths")
    for label, values in (
        ("project_original_skill_paths", project_paths),
        ("third_party_paths", third_party_paths),
    ):
        if (
            not isinstance(values, list)
            or values != sorted(values)
            or len(values) != len(set(values))
            or not all(_safe_locked_path(value) for value in values)
        ):
            raise ValueError(f"origin policy {label} is invalid")
    roster = {
        path.relative_to(root / skill_root).as_posix()
        for path in (root / skill_root).rglob("*")
        if path.is_file() and not any(part in WALK_IGNORES for part in path.parts)
    } if (root / skill_root).is_dir() else set()
    if not set(project_paths).issubset(roster):
        raise ValueError("origin policy project-original paths are not in the Skill roster")
    if payload.get("skill_path_roster_sha256") != _skill_roster_sha256(root, skill_root):
        raise ValueError("origin policy Skill path roster changed")
    return payload


def expected_origin(path: str, policy: dict[str, object]) -> str:
    third_party_paths = set(policy["third_party_paths"])
    if path in third_party_paths:
        return "third-party-licensed"
    skill_root = PurePosixPath(str(policy["skill_root"]))
    pure = PurePosixPath(path)
    if pure == skill_root or skill_root in pure.parents:
        relative = pure.relative_to(skill_root).as_posix()
        if relative in set(policy["project_original_skill_paths"]):
            return "project-original"
        return "adapted-mit-upstream"
    return "project-original"


def _git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def verify_upstream_map(
    root: Path,
    hashes: dict[str, str],
    policy: dict[str, object],
) -> list[Issue]:
    """Verify a self-contained path/blob map for every adapted Skill file."""
    path = root / UPSTREAM_MAP_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [Issue("upstream-map-invalid", UPSTREAM_MAP_PATH.as_posix(), str(exc))]
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "upstream",
        "adapted_files",
    }:
        return [
            Issue(
                "upstream-map-invalid",
                UPSTREAM_MAP_PATH.as_posix(),
                "invalid field set",
            )
        ]
    if payload.get("schema_version") != SCHEMA_VERSION:
        return [
            Issue(
                "upstream-map-invalid",
                UPSTREAM_MAP_PATH.as_posix(),
                "unsupported schema",
            )
        ]
    if payload.get("upstream") != policy.get("upstream"):
        return [
            Issue(
                "upstream-map-invalid",
                UPSTREAM_MAP_PATH.as_posix(),
                "upstream identity differs from origin policy",
            )
        ]
    declared = payload.get("adapted_files")
    if not isinstance(declared, dict):
        return [
            Issue(
                "upstream-map-invalid",
                UPSTREAM_MAP_PATH.as_posix(),
                "adapted_files must be an object",
            )
        ]

    skill_root = PurePosixPath(str(policy["skill_root"]))
    expected = {
        name
        for name in hashes
        if expected_origin(name, policy) == "adapted-mit-upstream"
    }
    issues: list[Issue] = []
    for name in sorted(expected - set(declared)):
        issues.append(Issue("upstream-map-missing", name, "adapted file is not mapped"))
    for name in sorted(set(declared) - expected):
        issues.append(Issue("upstream-map-stale", name, "mapped file is not adapted"))

    sha1_pattern = re.compile(r"[0-9a-f]{40}")
    for name in sorted(expected & set(declared)):
        record = declared[name]
        if not isinstance(record, dict) or set(record) != {
            "upstream_path",
            "upstream_git_blob_sha1",
            "relation",
        }:
            issues.append(Issue("upstream-map-invalid-record", name, "invalid field set"))
            continue
        relative = PurePosixPath(name).relative_to(skill_root)
        expected_path = (PurePosixPath("skills/ppt-master") / relative).as_posix()
        if record.get("upstream_path") != expected_path:
            issues.append(
                Issue("upstream-map-path-mismatch", name, f"expected {expected_path}")
            )
        upstream_blob = record.get("upstream_git_blob_sha1")
        if not isinstance(upstream_blob, str) or not sha1_pattern.fullmatch(upstream_blob):
            issues.append(Issue("upstream-map-invalid-record", name, "invalid blob SHA-1"))
            continue
        relation = record.get("relation")
        if relation not in {"identical", "modified"}:
            issues.append(Issue("upstream-map-invalid-record", name, "invalid relation"))
            continue
        local_blob = _git_blob_sha1((root / name).read_bytes())
        actual_relation = "identical" if local_blob == upstream_blob else "modified"
        if relation != actual_relation:
            issues.append(
                Issue(
                    "upstream-map-relation-mismatch",
                    name,
                    f"declared {relation}; actual {actual_relation}",
                )
            )
    return issues


def verify_provenance(root: Path, hashes: dict[str, str]) -> list[Issue]:
    try:
        payload = load_provenance(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [Issue("provenance-invalid", PROVENANCE_PATH.as_posix(), str(exc))]

    try:
        origin_policy = load_origin_policy(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [Issue("origin-policy-invalid", ORIGIN_POLICY_PATH.as_posix(), str(exc))]

    current = {path: digest for path, digest in hashes.items() if PurePosixPath(path) != PROVENANCE_PATH}
    declared = payload["files"]
    issues = verify_upstream_map(root, hashes, origin_policy)
    for path in sorted(set(current) - set(declared)):
        issues.append(Issue("provenance-missing", path, "file is not declared"))
    for path in sorted(set(declared) - set(current)):
        issues.append(Issue("provenance-stale", path, "declared file is missing"))
    for path in sorted(set(current) & set(declared)):
        record = declared[path]
        if not isinstance(record, dict):
            issues.append(Issue("provenance-invalid-record", path, "record must be an object"))
            continue
        if record.get("sha256") != current[path]:
            issues.append(Issue("provenance-hash-mismatch", path, "content changed"))
        if record.get("origin") not in ORIGIN_VALUES:
            issues.append(Issue("provenance-origin-invalid", path, str(record.get("origin"))))
        elif record.get("origin") != expected_origin(path, origin_policy):
            issues.append(Issue("provenance-origin-mismatch", path, "origin differs from locked policy"))
    return issues


def write_provenance(root: Path, hashes: dict[str, str]) -> None:
    origin_policy = load_origin_policy(root)
    records: dict[str, dict[str, str]] = {}
    for path, digest in sorted(hashes.items()):
        if PurePosixPath(path) == PROVENANCE_PATH:
            continue
        records[path] = {"sha256": digest, "origin": expected_origin(path, origin_policy)}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "policy": "clean-room-public-release-v1",
        "upstream": {
            "name": "hugohe3/ppt-master",
            "commit": "bbb323f0ebd6a6a230dd6063209326b53bfd2e1d",
            "license": "MIT",
        },
        "files": records,
    }
    target = root / PROVENANCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def build_report(root: Path, issues: list[Issue], hashes: dict[str, str], history: bool) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "root": root.name,
        "passed": not issues,
        "history_scanned": history,
        "file_count": len(hashes),
        "tree_sha256": sha256_bytes(
            "".join(f"{path}\0{digest}\n" for path, digest in sorted(hashes.items())).encode("utf-8")
        ),
        "issues": [asdict(issue) for issue in issues],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="release tree to scan")
    parser.add_argument("--history", action="store_true", help="scan every reachable Git blob")
    parser.add_argument("--require-provenance", action="store_true", help="verify the frozen file manifest")
    parser.add_argument("--write-provenance", action="store_true", help="replace the frozen file manifest")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"privacy gate: not a directory: {root}", file=sys.stderr)
        return 2

    issues, hashes = scan_worktree(root)
    if args.write_provenance:
        if issues:
            print("privacy gate: refusing to freeze a failing tree", file=sys.stderr)
        else:
            try:
                write_provenance(root, hashes)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(
                    Issue("origin-policy-invalid", ORIGIN_POLICY_PATH.as_posix(), str(exc))
                )
            else:
                issues, hashes = scan_worktree(root)
    if args.require_provenance:
        issues.extend(verify_provenance(root, hashes))
    if args.history:
        issues.extend(scan_history(root))

    report = build_report(root, issues, hashes, args.history)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(f"FAIL {issue.code}: {issue.path}: {issue.detail} [{issue.source}]")
        print(f"privacy gate: FAILED with {len(issues)} issue(s)")
    else:
        print(f"privacy gate: PASS ({len(hashes)} files)")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
