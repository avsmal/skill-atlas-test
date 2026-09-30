from skill_atlas.dedupe import dedupe
from skill_atlas.models import Skill


def _s(path, name):
    return Skill("r", name, "", "c", path)


def run(skills, contents=None):
    warnings = []
    contents = contents or {}
    out = dedupe(skills, read=lambda p: contents.get(p, b"same"), warn=warnings.append)
    return [s.path for s in out], warnings


def test_prefers_agents_and_keeps_order():
    paths, warnings = run([
        _s(".agents/skills/pdf/SKILL.md", "pdf"),
        _s(".claude/skills/pdf/SKILL.md", "pdf"),
        _s(".claude/skills/only-claude/SKILL.md", "only-claude"),
    ])
    assert paths == [".agents/skills/pdf/SKILL.md", ".claude/skills/only-claude/SKILL.md"]
    assert warnings == []


def test_matches_by_name_not_dir():
    paths, _ = run([_s(".agents/skills/a/SKILL.md", "x"), _s(".claude/skills/b/SKILL.md", "x")])
    assert paths == [".agents/skills/a/SKILL.md"]


def test_same_dir_different_names_are_kept():
    paths, _ = run([_s(".agents/skills/a/SKILL.md", "x"), _s(".claude/skills/a/SKILL.md", "y")])
    assert len(paths) == 2


def test_different_prefixes_are_kept():
    paths, _ = run([
        _s(".agents/skills/pdf/SKILL.md", "pdf"),
        _s("backend/.agents/skills/pdf/SKILL.md", "pdf"),
        _s("backend/.claude/skills/pdf/SKILL.md", "pdf"),
        _s("frontend/.claude/skills/pdf/SKILL.md", "pdf"),
    ])
    assert paths == [
        ".agents/skills/pdf/SKILL.md",
        "backend/.agents/skills/pdf/SKILL.md",
        "frontend/.claude/skills/pdf/SKILL.md",
    ]


def test_warns_when_contents_differ():
    paths, warnings = run(
        [_s(".agents/skills/pdf/SKILL.md", "pdf"), _s(".claude/skills/pdf/SKILL.md", "pdf")],
        {".agents/skills/pdf/SKILL.md": b"a", ".claude/skills/pdf/SKILL.md": b"b"},
    )
    assert paths == [".agents/skills/pdf/SKILL.md"]
    assert warnings == ["pdf: .agents and .claude copies differ; using .agents/skills/pdf/SKILL.md"]


def test_duplicates_within_one_agent_dir_are_kept():
    paths, _ = run([_s(".claude/skills/a/SKILL.md", "x"), _s(".claude/skills/b/SKILL.md", "x")])
    assert len(paths) == 2
