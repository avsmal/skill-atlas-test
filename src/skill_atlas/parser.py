"""Parse SKILL.md YAML frontmatter."""
from __future__ import annotations

from pathlib import Path

import yaml


class SkillParseError(Exception):
    pass


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return ``(yaml block, body)``; the body is everything after the closing ``---``."""
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillParseError("missing YAML frontmatter")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise SkillParseError("unterminated YAML frontmatter")


def parse_frontmatter(text: str) -> dict:
    block, _ = _split_frontmatter(text)
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


def parse_skill(path: Path) -> tuple[str, str, str]:
    """Return ``(name, description, content)``; name falls back to the parent dir.

    ``content`` is the file's body, after the YAML frontmatter, whitespace-trimmed.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    data = parse_frontmatter(text)
    _, body = _split_frontmatter(text)
    name = str(data.get("name") or path.parent.name).strip()
    description = " ".join(str(data.get("description") or "").split())
    return name, description, body.strip()
