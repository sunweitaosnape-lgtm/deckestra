#!/usr/bin/env python3
"""Verify every retained third-party file and the no-bundled-icons policy."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


EXPECTED_SHA256 = {
    "third_party/ppt-master/MIT.txt":
        "80cefc234c1ec12a8cece4344f16300c634fa03df7891686fcf979e3828f0921",
    "skills/build-editable-decks/third_party/ppt-master/MIT.txt":
        "80cefc234c1ec12a8cece4344f16300c634fa03df7891686fcf979e3828f0921",
    "skills/build-editable-decks/scripts/pptx_shapes/data/presetShapeDefinitions.xml":
        "4a762444d8d85876881c02a5b1dedf6f73006fcd8acb7b4e393435615b37c780",
    "skills/build-editable-decks/scripts/pptx_shapes/data/shape_type_values.txt":
        "f2c3bdcda8569b358ce3196cfeb183849e33bfc7955fac961dc85fceb6b3b587",
    "skills/build-editable-decks/scripts/pptx_shapes/data/LICENSE-APACHE-2.0.txt":
        "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    "skills/build-editable-decks/scripts/pptx_shapes/data/LICENSE-OPEN-XML-SDK-MIT.txt":
        "cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310",
}

NOTICE_PATH = (
    "skills/build-editable-decks/scripts/pptx_shapes/data/NOTICE.md"
)
NOTICE_REQUIRED = (
    "Apache POI",
    "Copyright 2003-2025 The Apache Software Foundation",
    "Copyright (c) 2000-2003, BEA Systems",
    "REL_5_4_1",
    "4554f204cbbf00ecbcaed134fe57e43a1779a612",
    "00967dc871f06776ae969762c6703d062308a6c9",
    EXPECTED_SHA256[
        "skills/build-editable-decks/scripts/pptx_shapes/data/presetShapeDefinitions.xml"
    ],
    EXPECTED_SHA256[
        "skills/build-editable-decks/scripts/pptx_shapes/data/shape_type_values.txt"
    ],
)

ICON_ROOT = Path("skills/build-editable-decks/templates/icons")
FORBIDDEN_ICON_PACKAGE_NAMES = {
    "chunk",
    "chunk-filled",
    "phosphor",
    "phosphor-duotone",
    "simple-icons",
    "simpleicons",
    "tabler",
    "tabler-filled",
    "tabler-outline",
}

FORBIDDEN_UNREVIEWED_FILES = {
    "skills/build-editable-decks/scripts/pptx_animation_presets.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(root: Path) -> list[str]:
    root = root.resolve()
    issues: list[str] = []

    for relative in sorted(FORBIDDEN_UNREVIEWED_FILES):
        if (root / relative).exists():
            issues.append(
                "unreviewed-generated-data: "
                f"{relative} must not be included without documented capture "
                "and redistribution approval"
            )

    for relative, expected in EXPECTED_SHA256.items():
        path = root / relative
        if not path.is_file():
            issues.append(f"missing-license-file: {relative}")
            continue
        actual = sha256(path)
        if actual != expected:
            issues.append(
                f"third-party-hash-mismatch: {relative} expected={expected} actual={actual}"
            )

    notice = root / NOTICE_PATH
    if not notice.is_file():
        issues.append(f"missing-notice: {NOTICE_PATH}")
    else:
        notice_text = notice.read_text(encoding="utf-8")
        for required in NOTICE_REQUIRED:
            if required not in notice_text:
                issues.append(f"incomplete-notice: {NOTICE_PATH} missing {required!r}")

    icons = root / ICON_ROOT
    if not icons.is_dir():
        issues.append(f"missing-policy-directory: {ICON_ROOT.as_posix()}")
    else:
        entries = sorted(
            path.relative_to(icons).as_posix()
            for path in icons.rglob("*")
            if path.is_file()
        )
        if entries != ["README.md"]:
            issues.append(
                "bundled-icon-assets: expected templates/icons to contain only README.md; "
                f"found {entries!r}"
            )

    for path in root.rglob("*"):
        if any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        lowered = {part.casefold() for part in path.parts}
        hit = sorted(lowered & FORBIDDEN_ICON_PACKAGE_NAMES)
        if hit and ICON_ROOT not in path.parents and path != root / ICON_ROOT:
            issues.append(
                f"forbidden-vendored-icon-package: {path.relative_to(root).as_posix()} ({hit[0]})"
            )

    return sorted(set(issues))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify pinned third-party data and reject bundled icon packages."
    )
    parser.add_argument("root", nargs="?", default=".", help="Repository root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    issues = audit(Path(args.root))
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    print(
        f"[PASS] license gate: {len(EXPECTED_SHA256)} pinned files; "
        "no bundled icons or unreviewed generated data"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
