"""Locate the project's own skills in a checked-out repository.

Implements rules (a) location and (b) exclusions from spec/cli.md:
only ``<prefix>/{.agents,.claude}/skills/<skill-dir>/SKILL.md`` counts, and not
when ``<prefix>`` contains a shipped-resource, test, vendored or build directory.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SKILL_FILENAME = "skill.md"
AGENT_DIRS = (".agents", ".claude")
SKILLS_DIR = "skills"
EXCLUDED_SEGMENTS = frozenset({
    # skills shipped to users (e.g. inside a plugin)
    "resources",
    # the project's own tests
    "test", "tests", "testdata", "test-data", "fixtures", "__tests__",
    # vendored code and build output
    "node_modules", "vendor", "build", "out", "dist",
})


@dataclass(frozen=True)
class SkillLocation:
    """A candidate path split as ``<prefix>/<agent_dir>/skills/<skill_dir>/SKILL.md``."""

    prefix: tuple[str, ...]
    agent_dir: str
    skill_dir: str


def split_skill_path(rel_path: str | PurePosixPath) -> SkillLocation | None:
    """Apply rule (a); return the path's parts, or None if it isn't a skill location."""
    parts = PurePosixPath(rel_path).parts
    if len(parts) < 4:
        return None
    *prefix, agent_dir, skills, skill_dir, filename = parts
    if filename.lower() != SKILL_FILENAME or skills != SKILLS_DIR or agent_dir not in AGENT_DIRS:
        return None
    return SkillLocation(tuple(prefix), agent_dir, skill_dir)


def is_excluded(prefix: tuple[str, ...]) -> bool:
    """Apply rule (b) to ``<prefix>`` (case-insensitive)."""
    lowered = [p.lower() for p in prefix]
    for i, seg in enumerate(lowered):
        if seg in EXCLUDED_SEGMENTS:
            return True
        if seg.startswith("test") and i > 0 and lowered[i - 1] == "src":
            return True
    return False


def is_skill_path(rel_path: str | PurePosixPath) -> bool:
    loc = split_skill_path(rel_path)
    return loc is not None and not is_excluded(loc.prefix)


@dataclass
class Discovery:
    files: list[Path] = field(default_factory=list)
    symlinks: list[Path] = field(default_factory=list)


def find_skill_files(root: Path) -> Discovery:
    """Walk ``root`` (without following symlinked dirs) and apply rules (a) and (b).

    Symlinked SKILL.md files that would otherwise count are returned in
    ``symlinks`` so the caller can warn about them.
    """
    result = Discovery()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for fn in sorted(filenames):
            path = Path(dirpath) / fn
            if not is_skill_path(path.relative_to(root).as_posix()):
                continue
            (result.symlinks if path.is_symlink() else result.files).append(path)
    return result
