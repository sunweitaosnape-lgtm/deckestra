#!/usr/bin/env python3
"""Build and revalidate a deterministic certified Deckestra source ZIP."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import privacy_gate


ARCHIVE_ROOT = "deckestra"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class ReleaseBuildError(RuntimeError):
    """Raised when a source package cannot be built safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    if not output.is_absolute():
        raise ReleaseBuildError("--output must be an absolute path outside the repository")
    resolved = output.resolve()
    if resolved == root or root in resolved.parents:
        raise ReleaseBuildError("release archives must be written outside the repository")
    if resolved.suffix.lower() != ".zip":
        raise ReleaseBuildError("release output must use the .zip suffix")
    if resolved.exists():
        raise ReleaseBuildError(f"refusing to overwrite existing output: {resolved}")
    return resolved


def archive_mode(data: bytes) -> int:
    return 0o755 if data.startswith(b"#!") else 0o644


def write_archive(root: Path, destination: Path, hashes: dict[str, str]) -> None:
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for relative in sorted(hashes):
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts:
                raise ReleaseBuildError(f"unsafe archive path: {relative}")
            data = (root / relative).read_bytes()
            if privacy_gate.sha256_bytes(data) != hashes[relative]:
                raise ReleaseBuildError(f"source changed during packaging: {relative}")
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{relative}", date_time=FIXED_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | archive_mode(data)) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def safe_extract(archive_path: Path, destination: Path) -> Path:
    expected_root = destination / ARCHIVE_ROOT
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or not pure.parts or pure.parts[0] != ARCHIVE_ROOT or ".." in pure.parts:
                raise ReleaseBuildError(f"unsafe packaged path: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
                raise ReleaseBuildError(f"non-regular packaged entry: {info.filename}")
        archive.extractall(destination)
    if not expected_root.is_dir():
        raise ReleaseBuildError("archive is missing its source root")
    return expected_root


def run_gate(root: Path, *, history: bool) -> None:
    command = [
        sys.executable,
        str(Path(__file__).with_name("release_gate.py")),
        str(root),
        "--require-provenance",
    ]
    if history:
        command.append("--history")
    process = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, check=False)
    if process.returncode:
        scope = "source history" if history else "extracted package"
        raise ReleaseBuildError(f"{scope} release gate failed")


def run_certification(root: Path, evidence: Path) -> None:
    command = [
        sys.executable,
        str(Path(__file__).with_name("certification_gate.py")),
        "--root",
        str(root),
        "--evidence",
        str(evidence),
    ]
    process = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, check=False)
    if process.returncode:
        raise ReleaseBuildError("frozen blind certification gate failed")


def verify_extracted_tree(root: Path, expected_hashes: dict[str, str]) -> None:
    issues, actual_hashes = privacy_gate.scan_worktree(root)
    if issues:
        raise ReleaseBuildError(f"extracted tree failed privacy scan with {len(issues)} issue(s)")
    if actual_hashes != expected_hashes:
        missing = sorted(set(expected_hashes) - set(actual_hashes))
        extra = sorted(set(actual_hashes) - set(expected_hashes))
        changed = sorted(
            path
            for path in set(actual_hashes) & set(expected_hashes)
            if actual_hashes[path] != expected_hashes[path]
        )
        raise ReleaseBuildError(
            f"extracted tree mismatch: missing={missing}, extra={extra}, changed={changed}"
        )


def build(root: Path, output: Path, certification_evidence: Path) -> tuple[str, int]:
    root = root.resolve()
    if not root.is_dir():
        raise ReleaseBuildError(f"not a directory: {root}")
    output = validate_output(root, output)

    run_gate(root, history=True)
    run_certification(root, certification_evidence)
    issues, hashes = privacy_gate.scan_worktree(root)
    if issues:
        raise ReleaseBuildError(f"source privacy scan failed with {len(issues)} issue(s)")

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".deckestra-release-",
        suffix=".zip.tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary_archive = Path(temporary_name)
    try:
        write_archive(root, temporary_archive, hashes)
        with tempfile.TemporaryDirectory(prefix="deckestra-release-check-") as temporary:
            extracted = safe_extract(temporary_archive, Path(temporary))
            verify_extracted_tree(extracted, hashes)
            run_gate(extracted, history=False)
            run_certification(extracted, certification_evidence)
        digest = sha256_file(temporary_archive)
        os.replace(temporary_archive, output)
    except Exception:
        temporary_archive.unlink(missing_ok=True)
        raise
    return digest, len(hashes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--output", type=Path, required=True, help="absolute external .zip path")
    parser.add_argument(
        "--certification-evidence",
        type=Path,
        required=True,
        help="absolute external evidence JSON that passes the frozen blind gate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        digest, file_count = build(Path(args.root), args.output, args.certification_evidence)
    except (OSError, ReleaseBuildError, zipfile.BadZipFile) as exc:
        print(f"[FAIL] release build: {exc}", file=sys.stderr)
        return 1
    output = args.output.resolve()
    print(f"[PASS] release archive: files={file_count} sha256={digest} path={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
