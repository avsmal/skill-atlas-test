from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Skill:
    repo: str
    name: str
    description: str
    commit: str
    path: str
    # paths of .claude copies merged into this skill by rule (c), in path order
    duplicates: tuple[str, ...] = ()
    # the SKILL.md body, after the YAML frontmatter; used for similarity (see spec/web.md)
    content: str = ""

    def to_dict(self) -> dict:
        return {**asdict(self), "duplicates": list(self.duplicates)}


@dataclass(frozen=True)
class RepoEntry:
    """A scanned repository, as listed in the web catalogue."""

    repo: str
    commit: str
    scanned_at: str  # ISO-8601 UTC
    skills: int
