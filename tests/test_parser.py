import pytest

from skill_atlas.parser import SkillParseError, parse_frontmatter, parse_skill


def test_parse_frontmatter():
    assert parse_frontmatter("---\nname: a\ndescription: b\n---\nbody") == {"name": "a", "description": "b"}


@pytest.mark.parametrize("text", ["no fm", "---\nname: a\n", "---\n- a\n---\n", "---\nname: [\n---\n"])
def test_parse_frontmatter_invalid(text):
    with pytest.raises(SkillParseError):
        parse_frontmatter(text)


def test_parse_skill_name_fallback_and_whitespace(tmp_path):
    d = tmp_path / "my-skill"
    d.mkdir()
    p = d / "SKILL.md"
    p.write_text("---\ndescription: |\n  multi\n  line\n---\n")
    assert parse_skill(p) == ("my-skill", "multi line", "")


def test_parse_skill_content_is_the_body(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: a\n---\n\nSome instructions.\n\nMore text.\n")
    assert parse_skill(p) == ("a", "", "Some instructions.\n\nMore text.")
