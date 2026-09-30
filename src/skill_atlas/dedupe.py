"""Rule (c) from spec/cli.md: merge .agents/.claude copies of the same skill."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .discovery import split_skill_path
from .models import Skill


def dedupe(
    skills: list[Skill],
    read: Callable[[str], bytes],
    warn: Callable[[str], None],
) -> list[Skill]:
    """Drop ``.claude`` skills that share a name with a ``.agents`` skill in the same prefix.

    ``read(path)`` returns a skill file's contents; when the dropped copy differs
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
    for key, kept in agents.items():
        for s in by_key[key]:
            loc = split_skill_path(s.path)
            if loc.agent_dir != ".claude":
                continue
            dropped.add(s.path)
            if read(s.path) != read(kept.path):
                warn(f"{s.name}: .agents and .claude copies differ; using {kept.path}")
    return [s for s in skills if s.path not in dropped]
