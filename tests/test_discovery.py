from skill_atlas.discovery import find_skill_files


def test_find_skill_files(tmp_path):
    for rel in ["a/SKILL.md", "b/c/skill.md", ".git/x/SKILL.md", "d/OTHER.md"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    found = [p.relative_to(tmp_path).as_posix() for p in find_skill_files(tmp_path)]
    assert found == ["a/SKILL.md", "b/c/skill.md"]
