"""Rule (c) from spec/cli.md: merge .agents/.claude copies of the same skill."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Callable

from .discovery import split_skill_path
from .models import Skill


def dedupe(
    skills: list[Skill],
    read: Callable[[str], bytes],
    warn: Callable[[str], None],
) -> list[Skill]:
    """Drop ``.claude`` skills that share a name with a ``.agents`` skill in the same prefix.

    The kept ``.agents`` skill lists the dropped paths in ``duplicates``. ``read(path)`` returns a skill file's contents; when the dropped copy differs
    from the kept one, ``warn`` is called. Order of the remaining skills is kept.
    """
    agents: dict[tuple, Skill] = {}
    by_key: dict[tuple, list[Skill]] = defaultdict(list)
    for s in skills:
        loc = split_skill_path(s.path)
        key = (loc.prefix, s.name) if loc else (None, s.path)
        by_key[key].append(s)
        if loc and loc.agent_dir == ".agents":
            agents.setdefault(key, s)

    dropped: set[str] = set()
    merged: dict[str, Skill] = {}
    for key, kept in agents.items():
        copies = [s.path for s in by_key[key] if split_skill_path(s.path).agent_dir == ".claude"]
        for path in copies:
            dropped.add(path)
            if read(path) != read(kept.path):
                warn(f"{kept.name}: .agents and .claude copies differ; using {kept.path}")
        if copies:
            merged[kept.path] = replace(kept, duplicates=kept.duplicates + tuple(copies))
    return [merged.get(s.path, s) for s in skills if s.path not in dropped]
