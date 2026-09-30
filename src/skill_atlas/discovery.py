"""Locate SKILL.md files in a checked-out repository."""
from __future__ import annotations

import os
from pathlib import Path

SKILL_FILENAME = "skill.md"
_SKIP_DIRS = {".git", "node_modules"}


def find_skill_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.lower() == SKILL_FILENAME:
                found.append(Path(dirpath) / fn)
    return found
