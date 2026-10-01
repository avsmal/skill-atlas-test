"""Human-readable, optionally colored rendering of skills."""
from __future__ import annotations

import os
import shutil
import sys
import textwrap
from typing import Callable, TextIO

from .models import Skill
from .repo import github_blob_url

_CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
}


def use_color(mode: str, stream: TextIO) -> bool:
    """Resolve ``--color auto|always|never`` (auto honors NO_COLOR/FORCE_COLOR/TTY)."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return stream.isatty() and os.environ.get("TERM") != "dumb"


class Painter:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        codes = ";".join(_CODES[s] for s in styles)
        return f"\033[{codes}m{text}\033[0m"

    def link(self, text: str, url: str | None, *styles: str, external: bool = True) -> str:
        """``text`` linking to ``url``; the terminal shows just the styled text."""
        return self(text, *styles)


def render_skills(
    skills: list[Skill],
    paint: Painter,
    *,
    show_source: bool = False,
    width: int | None = None,
    name_url: Callable[[Skill], str | None] | None = None,
    name_suffix: Callable[[Skill], str] | None = None,
    wrap: Callable[[Skill, str], str] | None = None,
) -> str:
    """Numbered entries, one field per line; long descriptions are wrapped.

    ``show_source`` adds the repo and commit lines (used by ``list``, where
    entries may come from several repositories). ``name_url(skill)``, when given, links
    each skill's name (used by the web UI's *Similar skills*; the terminal ignores it, like
    the path's GitHub link). ``name_suffix(skill)``, when given, is markup appended right after
    the name (used by the web UI for the star button; it must add no text).

    ``wrap``, if given, wraps each skill's rendered block (used by the web UI to
    attach a searchable container around it without changing the plain text).
    """
    if width is None:
        width = shutil.get_terminal_size((100, 24)).columns
    num_w = len(str(len(skills)))
    indent = " " * (num_w + 2)
    labels = ["description", "path"] + (["repo", "commit"] if show_source else [])
    label_w = max(map(len, labels)) + 1  # + colon
    pad = " " * (len(indent) + label_w + 1)

    def field(
        label: str, value: str, *styles: str, wrap: bool = False, url: str | None = None,
    ) -> list[str]:
        head = indent + paint((label + ":").ljust(label_w), "dim") + " "
        lines = textwrap.wrap(value, max(20, width - len(pad))) if wrap else [value]
        lines = lines or [""]
        first = paint.link(lines[0], url, *styles)
        return [head + first] + [pad + paint(l, *styles) for l in lines[1:]]

    def path_line(s: Skill, path: str) -> str:
        return paint.link(path, github_blob_url(s.repo, s.commit, path), "green")

    blocks = []
    for i, s in enumerate(skills, 1):
        number = paint(f"{i:>{num_w}}.", "yellow")
        name = paint.link(s.name, name_url(s) if name_url else None, "bold", "cyan", external=False)
        suffix = name_suffix(s) if name_suffix else ""
        lines = [f"{number} {name}{suffix}"]
        lines += field("description", s.description or "—", wrap=True)
        lines += field("path", s.path, "green", url=github_blob_url(s.repo, s.commit, s.path))
        lines += [pad + path_line(s, p) for p in s.duplicates]  # merged .claude copies (rule c)
        if show_source:
            lines += field("repo", s.repo, "blue")
            lines += field("commit", s.commit, "magenta")
        blocks.append("\n".join(lines))
    if wrap is None:
        return "\n\n".join(blocks)
    last = len(blocks) - 1
    return "".join(
        wrap(s, block if i == last else block + "\n\n")
        for i, (s, block) in enumerate(zip(skills, blocks))
    )


def render_header(repo: str, commit: str, paint: Painter) -> str:
    return f"{paint(repo, 'bold', 'blue')} {paint('@', 'dim')} {paint(commit[:12], 'magenta')}"


def render_list(
    skills: list[Skill],
    paint: Painter,
    *,
    width: int | None = None,
    name_url: Callable[[Skill], str | None] | None = None,
    name_suffix: Callable[[Skill], str] | None = None,
    wrap: Callable[[Skill, str], str] | None = None,
) -> str:
    """What ``skill-atlas list`` prints: entries with their repo and commit, then a summary."""
    if not skills:
        return paint("No skills stored", "yellow")
    entries = render_skills(
        skills, paint, show_source=True, width=width, name_url=name_url, name_suffix=name_suffix, wrap=wrap,
    )
    return f"{entries}\n\n{paint(f'{len(skills)} skill(s) stored', 'bold', 'green')}"


def render_summary(count: int, paint: Painter) -> str:
    if count == 0:
        return paint("No skills found", "yellow")
    return paint(f"{count} skill(s) found", "bold", "green")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def render_owner_header(owner: str, repos: int, forks: int, paint: Painter) -> str:
    """``https://github.com/<owner>: N repositories (K forks skipped)`` for an organization scan."""
    line = f"{paint(owner, 'bold', 'blue')}: {_plural(repos, 'repository', 'repositories')}"
    if forks:
        line += paint(f" ({_plural(forks, 'fork', 'forks')} skipped)", "dim")
    return line


def render_owner_summary(skills: int, with_skills: int, repos: int, failed: int, paint: Painter) -> str:
    total = _plural(repos, "repository", "repositories")
    tail = f" ({failed} failed)" if failed else ""
    if skills == 0:
        return paint(f"No skills found in {total}{tail}", "yellow")
    return paint(f"{skills} skill(s) found in {with_skills} of {total}{tail}", "bold", "green")


def warn(msg: str, stream: TextIO | None = None) -> None:
    stream = stream or sys.stderr
    paint = Painter(use_color("auto", stream))
    print(f"{paint('warning:', 'bold', 'yellow')} {msg}", file=stream)


def error(msg: str, stream: TextIO | None = None) -> None:
    stream = stream or sys.stderr
    paint = Painter(use_color("auto", stream))
    print(f"{paint('error:', 'bold', 'red')} {msg}", file=stream)
