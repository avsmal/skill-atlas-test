import io

from skill_atlas.models import Skill
from skill_atlas.output import Painter, render_skills, use_color


def test_use_color(monkeypatch):
    tty = io.StringIO()
    tty.isatty = lambda: True
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    assert use_color("auto", tty)
    assert not use_color("auto", io.StringIO())
    assert not use_color("never", tty)
    assert use_color("always", io.StringIO())
    monkeypatch.setenv("NO_COLOR", "1")
    assert not use_color("auto", tty)


def test_render_wraps_description_and_pads_numbers():
    skills = [Skill("r", f"s{i}", "word " * 30, "c", f"p{i}") for i in range(10)]
    out = render_skills(skills, Painter(False), width=60)
    lines = out.splitlines()
    assert lines[0] == " 1. s0"
    assert all(len(l) <= 60 for l in lines)
    assert lines[2].startswith(" " * 17 + "word")  # wrapped continuation aligned with value
    assert "10. s9" in out


def test_render_lists_duplicate_paths_aligned():
    s = Skill("r", "pdf", "d", "c", ".agents/skills/pdf/SKILL.md", (".claude/skills/pdf/SKILL.md",))
    assert render_skills([s], Painter(False)).splitlines()[2:] == [
        "   path:        .agents/skills/pdf/SKILL.md",
        "                .claude/skills/pdf/SKILL.md",
    ]
