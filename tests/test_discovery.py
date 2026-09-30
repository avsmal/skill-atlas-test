import pytest

from skill_atlas.discovery import SkillLocation, find_skill_files, is_excluded, is_skill_path, split_skill_path


def test_split_skill_path():
    assert split_skill_path("backend/api/.claude/skills/x/SKILL.md") == SkillLocation(("backend", "api"), ".claude", "x")
    assert split_skill_path(".agents/skills/x/skill.md") == SkillLocation((), ".agents", "x")


@pytest.mark.parametrize("path", [
    ".claude/skills/x/SKILL.md",
    ".agents/skills/x/SKILL.md",
    ".claude/skills/x/skill.md",
    ".claude/skills/x/Skill.md",
    "a/b/c/.claude/skills/x/SKILL.md",
    ".claude/skills/test/SKILL.md",       # rule (b) looks at the prefix only
    ".claude/skills/resources/SKILL.md",
    "src/main/.claude/skills/x/SKILL.md",
    "latest/.claude/skills/x/SKILL.md",   # 'test' substring is not a test dir
    "contest/.claude/skills/x/SKILL.md",
])
def test_is_skill_path_accepts(path):
    assert is_skill_path(path)


@pytest.mark.parametrize("path", [
    "SKILL.md",
    "skills/x/SKILL.md",
    "plugins/p/skills/x/SKILL.md",
    ".claude/skills/SKILL.md",
    ".claude/skills/a/b/SKILL.md",
    ".claude/SKILL.md",
    ".claude/skill/x/SKILL.md",
    ".claude/Skills/x/SKILL.md",
    ".Claude/skills/x/SKILL.md",
    "claude/skills/x/SKILL.md",
    ".github/skills/x/SKILL.md",
    ".claude/skills/x/SKILL.md.bak",
    ".claude/skills/x/skills.md",
    ".claude/skills/x/MY_SKILL.md",
    ".claude/skills/x/README.md",
])
def test_is_skill_path_rejects_location(path):
    assert not is_skill_path(path)


@pytest.mark.parametrize("prefix", [
    "resources", "test", "tests", "testdata", "test-data", "fixtures", "__tests__",
    "node_modules", "vendor", "build", "out", "dist",
    "Resources", "TestData", "TESTS", "BUILD",
    "src/test", "src/testFixtures", "src/testIntegration", "src/TestKit",
    "plugin/src/main/resources", "src/test/resources", "compiler/testData",
    "node_modules/pkg", "a/b/fixtures/c",
])
def test_is_excluded(prefix):
    parts = tuple(prefix.split("/"))
    assert is_excluded(parts)
    assert not is_skill_path(f"{prefix}/.claude/skills/x/SKILL.md")


@pytest.mark.parametrize("prefix", ["", "backend", "src", "src/main", "testing-docs", "lib/tester", "latest", "outputs"])
def test_not_excluded(prefix):
    assert not is_excluded(tuple(p for p in prefix.split("/") if p))


def test_find_skill_files(tmp_path):
    for rel in [
        ".claude/skills/a/SKILL.md",
        "sub/.agents/skills/b/skill.md",
        ".git/.claude/skills/c/SKILL.md",
        "tests/.claude/skills/d/SKILL.md",
        "skills/e/SKILL.md",
    ]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    (tmp_path / ".claude/skills/link").mkdir()
    (tmp_path / ".claude/skills/link/SKILL.md").symlink_to("../a/SKILL.md")
    found = find_skill_files(tmp_path)
    assert [p.relative_to(tmp_path).as_posix() for p in found.files] == [
        ".claude/skills/a/SKILL.md",
        "sub/.agents/skills/b/skill.md",
    ]
    assert [p.relative_to(tmp_path).as_posix() for p in found.symlinks] == [".claude/skills/link/SKILL.md"]


def test_find_skill_files_does_not_follow_symlinked_dirs(tmp_path):
    (tmp_path / ".agents/skills/a").mkdir(parents=True)
    (tmp_path / ".agents/skills/a/SKILL.md").write_text("")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/skills").symlink_to("../.agents/skills")
    found = find_skill_files(tmp_path)
    assert [p.relative_to(tmp_path).as_posix() for p in found.files] == [".agents/skills/a/SKILL.md"]
    assert found.symlinks == []
