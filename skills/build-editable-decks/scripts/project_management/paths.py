#!/usr/bin/env python3
"""
Deckestra - Project Management Paths

Own the repository and Skill resource roots used by project-management modules.

Usage:
    Import the required path constants from project_management.paths.

Examples:
    from project_management.paths import PROJECTS_ROOT, SCHEMA_DIR

Dependencies:
    None (only uses the standard library)
"""

import os
import tempfile
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PACKAGE_DIR.parent
SKILL_DIR = SCRIPTS_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent


def _default_workspace_root() -> Path:
    configured = os.environ.get("DECKESTRA_WORKSPACE_ROOT", "").strip()
    root = (
        Path(configured).expanduser()
        if configured
        else Path(tempfile.gettempdir()) / "deckestra-workspaces"
    )
    return root.resolve(strict=False)


def require_external_workspace(path: str | Path) -> Path:
    """Reject runtime data anywhere inside the distributed source package."""
    resolved = Path(path).expanduser().resolve(strict=False)
    repository = REPO_ROOT.resolve(strict=False)
    if resolved == repository or repository in resolved.parents:
        raise ValueError(
            "Runtime workspaces must stay outside the Deckestra source package"
        )
    return resolved


PROJECTS_ROOT = require_external_workspace(_default_workspace_root())
SOURCE_TO_MD_DIR = SCRIPTS_DIR / "source_to_md"
CHARTS_DIR = SKILL_DIR / "templates" / "charts"
SCHEMA_DIR = SKILL_DIR / "templates" / "schemas"
SCAFFOLD_DIR = SKILL_DIR / "templates" / "scaffolds"
