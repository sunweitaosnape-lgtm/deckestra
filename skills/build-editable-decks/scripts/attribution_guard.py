#!/usr/bin/env python3
"""Validate the self-contained Skill identity and required legal notices."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
ERROR = "Deckestra Skill integrity check failed. Use the complete distribution."
REQUIRED_FILES = (
    "SKILL.md",
    "LICENSE",
    "PRIVACY.md",
    "THIRD_PARTY_NOTICES.md",
    "third_party/ppt-master/MIT.txt",
)


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    return text[4:end]


def _integrity_is_valid() -> bool:
    if not all((SKILL_DIR / name).is_file() for name in REQUIRED_FILES):
        return False
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    fields = [
        match.group(1)
        for match in re.finditer(r"(?m)^([a-z][a-z0-9_-]*):", metadata)
    ]
    if fields != ["name", "description"]:
        return False
    if not re.search(r"(?m)^name:\s*build-editable-decks\s*$", metadata):
        return False
    legacy_name = "ppt" + "-master"
    if legacy_name in text.lower() or "certified" in text.lower():
        return False
    notice = (SKILL_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    upstream_license = (SKILL_DIR / "third_party/ppt-master/MIT.txt").read_text(encoding="utf-8")
    return (
        "Copyright (c) 2025-2026 Hugo He" in notice
        and "Copyright (c) 2025-2026 Hugo He" in upstream_license
        and "MIT License" in upstream_license
    )


def require_skill_integrity() -> None:
    try:
        valid = _integrity_is_valid()
    except (OSError, UnicodeError, ValueError):
        valid = False
    if not valid:
        print(ERROR, file=sys.stderr)
        raise SystemExit(78)


def main() -> int:
    require_skill_integrity()
    print("Deckestra Skill integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
