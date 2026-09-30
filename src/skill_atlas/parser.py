"""Parse SKILL.md YAML frontmatter."""
from __future__ import annotations

from pathlib import Path

import yaml


class SkillParseError(Exception):
    pass


def parse_frontmatter(text: str) -> dict:
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillParseError("missing YAML frontmatter")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            block = "\n".join(lines[1:i])
            break
    else:
        raise SkillParseError("unterminated YAML frontmatter")
    try:
        data = yaml.safe_load(block) or {}
    except yaml.YAMLError as e:
        raise SkillParseError(f"invalid YAML: {_describe_yaml_error(e)}") from e
    if not isinstance(data, dict):
        raise SkillParseError("frontmatter is not a mapping")
    return data


def _describe_yaml_error(e: yaml.YAMLError) -> str:
    """One-line summary of a PyYAML error; line numbers count the opening ``---``."""
    problem = getattr(e, "problem", None)
    mark = getattr(e, "problem_mark", None)
    if not problem:
        return str(e).splitlines()[0]
    return f"{problem} (line {mark.line + 2})" if mark else problem


def parse_skill(path: Path) -> tuple[str, str]:
    """Return ``(name, description)``; name falls back to the parent dir."""
    data = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    name = str(data.get("name") or path.parent.name).strip()
    description = " ".join(str(data.get("description") or "").split())
    return name, description
