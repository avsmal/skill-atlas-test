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

    def to_dict(self) -> dict:
        return {**asdict(self), "duplicates": list(self.duplicates)}
