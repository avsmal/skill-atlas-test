import json

from skill_atlas.cli import main


def test_scan_and_list(fixture_repo, tmp_path, capsys):
    db = tmp_path / "atlas.db"
    url = fixture_repo.as_uri()

    assert main(["scan", url, "--json", "--db", str(db)]) == 0
    out = capsys.readouterr()
    skills = json.loads(out.out)
    assert [(s["name"], s["description"], s["path"]) for s in skills] == [
        ("pdf", "Work with PDF files", ".claude/skills/pdf/SKILL.md"),
        ("review", "Review code carefully", "plugins/x/skills/review/SKILL.md"),
    ]
    assert all(len(s["commit"]) == 40 and s["repo"] == url for s in skills)
    assert "skipping broken/SKILL.md" in out.err

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
    assert "1. pdf\n   description: Work with PDF files\n   path:        .claude/skills/pdf/SKILL.md" in out
    assert "2. review\n" in out
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
