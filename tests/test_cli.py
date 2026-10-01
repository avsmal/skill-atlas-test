import json

from skill_atlas.cli import main


def test_scan_and_list(fixture_repo, tmp_path, capsys):
    db = tmp_path / "atlas.db"
    url = fixture_repo.as_uri()

    assert main(["scan", url, "--json", "--db", str(db)]) == 0
    out = capsys.readouterr()
    skills = json.loads(out.out)
    assert [(s["name"], s["description"], s["path"]) for s in skills] == [
        ("review", "Review code carefully", ".agents/skills/review/SKILL.md"),
        ("pdf", "Work with PDF files", ".claude/skills/pdf/SKILL.md"),
    ]
    assert all(len(s["commit"]) == 40 and s["repo"] == url for s in skills)
    assert "skipping .claude/skills/broken/SKILL.md" in out.err

    # rescan doesn't duplicate
    assert main(["scan", url, "--db", str(db)]) == 0
    assert "2 skill(s) found" in capsys.readouterr().out
    assert main(["list", "--json", "--db", str(db)]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_scan_no_store(fixture_repo, tmp_path, capsys):
    db = tmp_path / "atlas.db"
    assert main(["scan", fixture_repo.as_uri(), "--no-store", "--db", str(db)]) == 0
    assert not db.exists()


def test_scan_bad_repo(tmp_path, capsys):
    assert main(["scan", (tmp_path / "nope").as_uri(), "--db", str(tmp_path / "db")]) == 1
    assert "error:" in capsys.readouterr().err


def test_scan_text_output_numbered_multiline(fixture_repo, tmp_path, capsys):
    url = fixture_repo.as_uri()
    assert main(["scan", url, "--no-store", "--color", "never", "--db", str(tmp_path / "db")]) == 0
    out = capsys.readouterr().out
    assert "\033[" not in out
    assert "2. pdf\n   description: Work with PDF files\n   path:        .claude/skills/pdf/SKILL.md" in out
    assert "1. review\n" in out
    assert "2 skill(s) found" in out


def test_scan_color_always(fixture_repo, tmp_path, capsys):
    url = fixture_repo.as_uri()
    assert main(["scan", url, "--no-store", "--color", "always", "--db", str(tmp_path / "db")]) == 0
    assert "\033[1;36mpdf\033[0m" in capsys.readouterr().out


def test_list_shows_repo_and_commit(fixture_repo, tmp_path, capsys):
    db = str(tmp_path / "db")
    url = fixture_repo.as_uri()
    main(["scan", url, "--json", "--db", db])
    commit = json.loads(capsys.readouterr().out)[0]["commit"]
    assert main(["list", "--color", "never", "--db", db]) == 0
    out = capsys.readouterr().out
    assert f"   repo:        {url}\n   commit:      {commit}" in out


def test_duplicated_skill_shows_all_paths(tmp_path, capsys):
    from conftest import make_repo, skill_md

    repo = make_repo(tmp_path / "dup", {
        ".agents/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files"),
        ".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files"),
    })
    url, db = repo.as_uri(), str(tmp_path / "db")
    assert main(["scan", url, "--color", "never", "--db", db]) == 0
    assert (
        "1. pdf\n   description: Work with PDF files\n"
        "   path:        .agents/skills/pdf/SKILL.md\n"
        "                .claude/skills/pdf/SKILL.md\n\n1 skill(s) found"
    ) in capsys.readouterr().out

    assert main(["scan", url, "--json", "--no-store", "--db", db]) == 0
    [skill] = json.loads(capsys.readouterr().out)
    assert skill["path"] == ".agents/skills/pdf/SKILL.md"
    assert skill["duplicates"] == [".claude/skills/pdf/SKILL.md"]

    assert main(["list", "--color", "never", "--db", db]) == 0
    assert (
        "   path:        .agents/skills/pdf/SKILL.md\n"
        "                .claude/skills/pdf/SKILL.md\n   repo:"
    ) in capsys.readouterr().out
    assert main(["list", "--json", "--db", db]) == 0
    assert json.loads(capsys.readouterr().out)[0]["duplicates"] == [".claude/skills/pdf/SKILL.md"]


def test_scan_empty_repo(tmp_path, capsys):
    import subprocess

    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    db = tmp_path / "db"
    assert main(["scan", repo.as_uri(), "--db", str(db)]) == 1
    assert capsys.readouterr().err == "error: repository is empty\n"
    assert not db.exists()
