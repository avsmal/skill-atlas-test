"""End-to-end edge cases from spec/cli.md, "What counts as a skill".

Each test builds a local git repo and runs the real pipeline
(sparse clone → discovery → parse → dedupe), so the sparse-checkout
patterns and the discovery rules are exercised together.
"""
import json

import pytest

from skill_atlas.cli import main, scan_repo
from conftest import make_repo, skill_md


def scan(root):
    _, _, skills = scan_repo(root.as_uri())
    return [(s.name, s.path) for s in skills]


@pytest.fixture
def repo(tmp_path):
    counter = iter(range(1000))
    return lambda files, symlinks=None: make_repo(tmp_path / f"repo{next(counter)}", files, symlinks)


# --- Examples table, one test per row -------------------------------------------------

def test_claude_skill(repo):
    assert scan(repo({".claude/skills/pdf/SKILL.md": skill_md("pdf")})) == [("pdf", ".claude/skills/pdf/SKILL.md")]


def test_agents_skill(repo):
    assert scan(repo({".agents/skills/pdf/SKILL.md": skill_md("pdf")})) == [("pdf", ".agents/skills/pdf/SKILL.md")]


def test_identical_agents_and_claude_copies_reported_once(repo, capsys):
    same = skill_md("pdf", "Work with PDFs")
    root = repo({".agents/skills/pdf/SKILL.md": same, ".claude/skills/pdf/SKILL.md": same})
    assert scan(root) == [("pdf", ".agents/skills/pdf/SKILL.md")]
    assert capsys.readouterr().err == ""


def test_different_agents_and_claude_copies_warn(repo, capsys):
    root = repo({
        ".agents/skills/pdf/SKILL.md": skill_md("pdf", "new"),
        ".claude/skills/pdf/SKILL.md": skill_md("pdf", "old"),
    })
    _, _, skills = scan_repo(root.as_uri())
    assert [(s.path, s.description) for s in skills] == [(".agents/skills/pdf/SKILL.md", "new")]
    assert "pdf: .agents and .claude copies differ; using .agents/skills/pdf/SKILL.md" in capsys.readouterr().err


def test_monorepo_prefix(repo):
    root = repo({"backend/.claude/skills/deploy/SKILL.md": skill_md("deploy")})
    assert scan(root) == [("deploy", "backend/.claude/skills/deploy/SKILL.md")]


def test_same_name_under_different_prefixes_is_two_skills(repo):
    root = repo({
        "backend/.agents/skills/pdf/SKILL.md": skill_md("pdf"),
        ".agents/skills/pdf/SKILL.md": skill_md("pdf"),
    })
    assert scan(root) == [("pdf", ".agents/skills/pdf/SKILL.md"), ("pdf", "backend/.agents/skills/pdf/SKILL.md")]


def test_skill_dir_named_like_excluded_segment_counts(repo):
    root = repo({".claude/skills/test/SKILL.md": skill_md(), ".claude/skills/build/SKILL.md": skill_md()})
    assert scan(root) == [("build", ".claude/skills/build/SKILL.md"), ("test", ".claude/skills/test/SKILL.md")]


def test_skills_outside_agent_dirs_ignored(repo, capsys):
    root = repo({
        "skills/pdf/SKILL.md": skill_md("pdf"),
        "plugins/x/skills/pdf/SKILL.md": skill_md("pdf"),
        "docs/SKILL.md": skill_md("docs"),
        "SKILL.md": skill_md("root"),
    })
    assert scan(root) == []
    assert capsys.readouterr().err == ""  # ignored files are silent


def test_wrong_depth_ignored(repo):
    root = repo({".claude/skills/SKILL.md": skill_md("a"), ".claude/skills/a/b/SKILL.md": skill_md("b")})
    assert scan(root) == []


@pytest.mark.parametrize("path", [
    "plugin/src/main/resources/.claude/skills/x/SKILL.md",   # shipped to users
    "src/test/resources/.claude/skills/x/SKILL.md",          # tests
    "compiler/testData/.agents/skills/x/SKILL.md",
    "src/testFixtures/.claude/skills/x/SKILL.md",
    "web/__tests__/.claude/skills/x/SKILL.md",
    "node_modules/pkg/.claude/skills/x/SKILL.md",            # vendored
    "vendor/lib/.agents/skills/x/SKILL.md",
    "dist/.claude/skills/x/SKILL.md",                        # build output
])
def test_excluded_locations_ignored(repo, path):
    root = repo({path: skill_md("x"), ".claude/skills/kept/SKILL.md": skill_md("kept")})
    assert scan(root) == [("kept", ".claude/skills/kept/SKILL.md")]


def test_symlinked_skill_file_skipped(repo, capsys):
    root = repo(
        {".agents/skills/real/SKILL.md": skill_md("real")},
        {".claude/skills/real/SKILL.md": "../../../.agents/skills/real/SKILL.md",
         ".claude/skills/outside/SKILL.md": "/etc/hosts"},
    )
    assert scan(root) == [("real", ".agents/skills/real/SKILL.md")]
    err = capsys.readouterr().err
    assert "skipping .claude/skills/outside/SKILL.md: symlink" in err
    assert "skipping .claude/skills/real/SKILL.md: symlink" in err


# --- Further edge cases ---------------------------------------------------------------

def test_symlinked_claude_skills_dir_not_duplicated(repo, capsys):
    root = repo({".agents/skills/pdf/SKILL.md": skill_md("pdf")}, {".claude/skills": "../.agents/skills"})
    assert scan(root) == [("pdf", ".agents/skills/pdf/SKILL.md")]
    assert capsys.readouterr().err == ""


def test_skill_only_in_claude_kept_next_to_agents_pair(repo):
    root = repo({
        ".agents/skills/pdf/SKILL.md": skill_md("pdf"),
        ".claude/skills/pdf/SKILL.md": skill_md("pdf"),
        ".claude/skills/claude-only/SKILL.md": skill_md("claude-only"),
        ".agents/skills/agents-only/SKILL.md": skill_md("agents-only"),
    })
    assert scan(root) == [
        ("agents-only", ".agents/skills/agents-only/SKILL.md"),
        ("pdf", ".agents/skills/pdf/SKILL.md"),
        ("claude-only", ".claude/skills/claude-only/SKILL.md"),
    ]


def test_dedupe_by_frontmatter_name_across_dir_names(repo):
    root = repo({".agents/skills/pdf-v2/SKILL.md": skill_md("pdf"), ".claude/skills/pdf/SKILL.md": skill_md("pdf")})
    assert scan(root) == [("pdf", ".agents/skills/pdf-v2/SKILL.md")]


def test_name_fallback_to_skill_dir_used_for_dedupe(repo):
    root = repo({".agents/skills/pdf/SKILL.md": skill_md(), ".claude/skills/pdf/SKILL.md": skill_md()})
    assert scan(root) == [("pdf", ".agents/skills/pdf/SKILL.md")]


def test_monorepo_with_several_prefixes(repo):
    root = repo({
        ".agents/skills/pdf/SKILL.md": skill_md("pdf"),
        ".claude/skills/pdf/SKILL.md": skill_md("pdf"),
        "backend/.agents/skills/pdf/SKILL.md": skill_md("pdf"),
        "backend/.claude/skills/pdf/SKILL.md": skill_md("pdf"),
        "backend/.claude/skills/migrate/SKILL.md": skill_md("migrate"),
        "frontend/app/.claude/skills/pdf/SKILL.md": skill_md("pdf"),
        "frontend/app/tests/.claude/skills/pdf/SKILL.md": skill_md("pdf"),
    })
    assert scan(root) == [
        ("pdf", ".agents/skills/pdf/SKILL.md"),
        ("pdf", "backend/.agents/skills/pdf/SKILL.md"),
        ("migrate", "backend/.claude/skills/migrate/SKILL.md"),
        ("pdf", "frontend/app/.claude/skills/pdf/SKILL.md"),
    ]


def test_file_name_case_variants(repo):
    root = repo({
        ".claude/skills/a/skill.md": skill_md("a"),
        ".claude/skills/b/Skill.md": skill_md("b"),
        ".claude/skills/c/SKILL.md.bak": skill_md("c"),
        ".claude/skills/d/skills.md": skill_md("d"),
        ".claude/skills/e/SKILL.markdown": skill_md("e"),
    })
    assert scan(root) == [("a", ".claude/skills/a/skill.md"), ("b", ".claude/skills/b/Skill.md")]


@pytest.mark.parametrize("prefix", ["Resources", "TestData", "TESTS", "src/TestKit"])
def test_exclusions_case_insensitive(repo, prefix):
    assert scan(repo({f"{prefix}/.claude/skills/x/SKILL.md": skill_md("x")})) == []


def test_unusual_folder_names(repo):
    paths = [
        "my project/.claude/skills/with space/SKILL.md",
        "навыки/.agents/skills/ünï-🚀/SKILL.md",
        "-dash/.claude/skills/x.y/SKILL.md",
        "a/b/c/d/e/f/g/h/.claude/skills/deep/SKILL.md",
    ]
    root = repo({p: skill_md() for p in paths})
    assert sorted(p for _, p in scan(root)) == sorted(paths)


def test_directory_named_skill_md_is_not_a_skill(repo):
    root = repo({".claude/skills/x/SKILL.md/notes.txt": "hi", ".claude/skills/y/SKILL.md": skill_md("y")})
    assert scan(root) == [("y", ".claude/skills/y/SKILL.md")]


def test_malformed_skill_warns_and_is_not_deduped_against(repo, capsys):
    root = repo({".agents/skills/pdf/SKILL.md": "no frontmatter", ".claude/skills/pdf/SKILL.md": skill_md("pdf")})
    assert scan(root) == [("pdf", ".claude/skills/pdf/SKILL.md")]
    assert "skipping .agents/skills/pdf/SKILL.md" in capsys.readouterr().err


def test_frontmatter_variants(repo):
    root = repo({
        ".claude/skills/crlf/SKILL.md": b"---\r\nname: crlf\r\ndescription: a\r\n---\r\n",
        ".claude/skills/bom/SKILL.md": "﻿---\nname: bom\n---\n",
        ".claude/skills/bad-utf8/SKILL.md": b"---\nname: bad\ndescription: caf\xe9\n---\n",
        ".claude/skills/empty/SKILL.md": "---\n---\n",
    })
    assert scan(root) == [
        ("bad", ".claude/skills/bad-utf8/SKILL.md"),
        ("bom", ".claude/skills/bom/SKILL.md"),
        ("crlf", ".claude/skills/crlf/SKILL.md"),
        ("empty", ".claude/skills/empty/SKILL.md"),
    ]


# --- CLI-level: exit codes, store, refs -------------------------------------------------

def test_repo_with_no_workflow_skills(repo, tmp_path, capsys):
    root = repo({"skills/pdf/SKILL.md": skill_md("pdf")})
    assert main(["scan", root.as_uri(), "--color", "never", "--db", str(tmp_path / "db")]) == 0
    assert "No skills found" in capsys.readouterr().out


def test_rescan_after_dedupe_stores_one_row(repo, tmp_path, capsys):
    same = skill_md("pdf")
    root = repo({".agents/skills/pdf/SKILL.md": same, ".claude/skills/pdf/SKILL.md": same})
    db = str(tmp_path / "db")
    for _ in range(2):
        assert main(["scan", root.as_uri(), "--json", "--db", db]) == 0
    capsys.readouterr()
    assert main(["list", "--json", "--db", db]) == 0
    assert [s["path"] for s in json.loads(capsys.readouterr().out)] == [".agents/skills/pdf/SKILL.md"]
