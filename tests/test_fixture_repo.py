"""Scan the on-disk fixture repository ``tests/fixtures/edge-repo`` end to end.

The fixture holds every edge case from spec/cli.md ("What counts as a skill") in one
realistic tree. It is copied to a temp dir, committed as a git repo, and scanned
through a ``file://`` URL, so the whole pipeline runs: sparse clone → discovery →
parse → dedupe → store → output. Expected results live in ``edge-repo.expected.json``.

To add a case: add files under ``edge-repo/`` and classify every new path in the
expected JSON (``skills``, ``deduplicated`` or ``ignored``). ``test_every_fixture_file_is_classified``
fails otherwise.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from skill_atlas.cli import main, scan_repo

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "edge-repo"
EXPECTED = json.loads((FIXTURES / "edge-repo.expected.json").read_text(encoding="utf-8"))
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


@pytest.fixture(scope="module")
def edge_repo(tmp_path_factory) -> tuple[Path, str]:
    """The fixture tree committed as a local git repo; returns ``(path, commit_sha)``."""
    root = tmp_path_factory.mktemp("fixture") / "edge-repo"
    shutil.copytree(SOURCE, root, symlinks=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def scanned(edge_repo):
    """Scan once per module; returns ``(skills, warnings)``."""
    root, _ = edge_repo
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        _, _, skills = scan_repo(root.as_uri())
    warnings = [ANSI.sub("", line).removeprefix("warning: ") for line in err.getvalue().splitlines()]
    return skills, warnings


# --- Result matches the expected snapshot --------------------------------------------

def test_skills_match_expected(scanned):
    skills, _ = scanned
    actual = [{"name": s.name, "path": s.path, "description": s.description} for s in skills]
    assert actual == EXPECTED["skills"]


def test_warnings_match_expected(scanned):
    _, warnings = scanned
    assert warnings == EXPECTED["warnings"]


def test_commit_and_repo_recorded(edge_repo, scanned):
    root, commit = edge_repo
    skills, _ = scanned
    assert {s.commit for s in skills} == {commit}
    assert {s.repo for s in skills} == {root.as_uri()}


# --- Per-path checks, so a failure names the edge case --------------------------------

@pytest.mark.parametrize("path", [s["path"] for s in EXPECTED["skills"]])
def test_expected_skill_reported(scanned, path):
    assert path in {s.path for s in scanned[0]}


@pytest.mark.parametrize("path,reason", sorted(EXPECTED["ignored"].items()))
def test_ignored_path_not_reported(scanned, path, reason):
    assert path not in {s.path for s in scanned[0]}, reason


@pytest.mark.parametrize("dropped,kept", sorted(EXPECTED["deduplicated"].items()))
def test_claude_copy_deduplicated_into_agents(scanned, dropped, kept):
    paths = {s.path for s in scanned[0]}
    assert dropped not in paths
    assert kept in paths


def test_duplicate_names_across_prefixes_are_kept(scanned):
    pdf_paths = [s.path for s in scanned[0] if s.name == "pdf"]
    assert pdf_paths == [
        ".agents/skills/pdf/SKILL.md",
        "backend/.agents/skills/pdf/SKILL.md",
        "frontend/app/.claude/skills/pdf/SKILL.md",
    ]


def test_identical_copies_do_not_warn(scanned):
    _, warnings = scanned
    assert not any(w.startswith(("pdf:", "release:")) for w in warnings)


# --- Guards on the fixture itself -----------------------------------------------------

def _fixture_entries() -> set[str]:
    """Every file and symlink in the fixture (symlinked dirs are listed, not walked)."""
    entries = set()
    for dirpath, dirnames, filenames in os.walk(SOURCE):
        for name in filenames + [d for d in dirnames if (Path(dirpath) / d).is_symlink()]:
            entries.add((Path(dirpath) / name).relative_to(SOURCE).as_posix())
    return entries


def test_every_fixture_file_is_classified():
    classified = (
        {s["path"] for s in EXPECTED["skills"]}
        | set(EXPECTED["deduplicated"])
        | set(EXPECTED["ignored"])
    )
    entries = _fixture_entries()
    assert entries - classified == set(), "unclassified fixture files; add them to edge-repo.expected.json"
    assert classified - entries == set(), "expected JSON names files missing from the fixture"


def test_fixture_bytes_preserved():
    """Guards against git/editor normalization of the byte-level edge cases."""
    assert b"\r\n" in (SOURCE / ".claude/skills/crlf/SKILL.md").read_bytes()
    assert (SOURCE / ".claude/skills/bom/SKILL.md").read_bytes().startswith(b"\xef\xbb\xbf")
    assert (SOURCE / ".claude/skills/linked/SKILL.md").is_symlink()
    assert (SOURCE / "mirror/.claude/skills").is_symlink()


def test_sparse_checkout_skips_non_candidates(edge_repo):
    """Only .agents/.claude skill locations are downloaded; excluded dirs are filtered later."""
    from skill_atlas.repo import clone

    root, _ = edge_repo
    with clone(root.as_uri()) as (checkout, _):
        present = {p.relative_to(checkout).as_posix() for p in checkout.rglob("*") if ".git" not in p.parts}
    for path in ["skills/product/SKILL.md", "docs/SKILL.md", "README.md", ".claude/skills/backup/SKILL.md.bak"]:
        assert path not in present
    assert "node_modules/pkg/.claude/skills/v1/SKILL.md" in present  # checked out, then excluded by rule b


# --- Through the CLI ------------------------------------------------------------------

def test_cli_scan_json_and_store(edge_repo, tmp_path, capsys):
    root, commit = edge_repo
    db = str(tmp_path / "atlas.db")
    assert main(["scan", root.as_uri(), "--json", "--db", db]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [(s["name"], s["path"]) for s in out] == [(s["name"], s["path"]) for s in EXPECTED["skills"]]

    assert main(["scan", root.as_uri(), "--json", "--db", db]) == 0  # rescan: no duplicate rows
    capsys.readouterr()
    assert main(["list", "--json", "--db", db]) == 0
    stored = json.loads(capsys.readouterr().out)
    assert sorted(s["path"] for s in stored) == sorted(s["path"] for s in EXPECTED["skills"])
    assert {s["commit"] for s in stored} == {commit}


def test_cli_scan_text(edge_repo, tmp_path, capsys):
    root, _ = edge_repo
    n = len(EXPECTED["skills"])
    assert main(["scan", root.as_uri(), "--no-store", "--color", "never", "--db", str(tmp_path / "db")]) == 0
    out = capsys.readouterr().out
    assert f"{n} skill(s) found" in out
    assert re.findall(r"^\s*(\d+)\. ", out, re.M) == [str(i) for i in range(1, n + 1)]
    assert " 1. agents-only\n" in out  # numbers right-aligned to two digits
