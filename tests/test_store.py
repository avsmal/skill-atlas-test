from skill_atlas.models import Skill
from skill_atlas.store import Store


def test_replace_repo_is_idempotent(tmp_path):
    s1 = Skill("r", "a", "d", "c1", "a/SKILL.md")
    s2 = Skill("r", "b", "d", "c1", "b/SKILL.md")
    other = Skill("o", "x", "", "c9", "SKILL.md")
    with Store(tmp_path / "db.sqlite") as st:
        st.replace_repo("o", [other])
        st.replace_repo("r", [s1, s2])
        st.replace_repo("r", [s1])
        assert st.list("r") == [s1]
        assert st.list() == [other, s1]
