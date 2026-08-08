#!/usr/bin/env python3
"""Console encoding helpers for Deckestra CLI scripts."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import TextIO

from attribution_guard import require_skill_integrity
from workflow_transcript import install_auto_transcript


_SKILL_DIR = Path(__file__).resolve().parent.parent
def _require_package_identity() -> None:
    """Require the independent technical Skill name at the package boundary."""
    try:
        text = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise SystemExit(78)
    if "\nname: build-editable-decks\n" not in text[:4096]:
        raise SystemExit(78)


def _reconfigure_stream(stream: TextIO) -> TextIO:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream
    except AttributeError:
        buffer = getattr(stream, "buffer", None)
        if buffer is None:
            return stream
        return io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return stream


def configure_utf8_stdio() -> None:
    """Configure CLI streams and enable project-scoped output recording."""
    require_skill_integrity()
    _require_package_identity()
    sys.stdout = _reconfigure_stream(sys.stdout)
    sys.stderr = _reconfigure_stream(sys.stderr)
    install_auto_transcript()
