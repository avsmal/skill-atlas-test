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
