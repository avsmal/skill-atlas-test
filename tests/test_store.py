from skill_atlas.models import RepoEntry, Skill
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


def test_duplicates_round_trip(tmp_path):
    s = Skill("r", "pdf", "d", "c", ".agents/skills/pdf/SKILL.md", (".claude/skills/pdf/SKILL.md",))
    with Store(tmp_path / "db.sqlite") as st:
        st.replace_repo("r", [s])
    with Store(tmp_path / "db.sqlite") as st:
        assert st.list() == [s]


def test_old_db_gets_duplicates_column(tmp_path):
    import sqlite3

    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE skills (repo TEXT NOT NULL, path TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
                             commit_sha TEXT NOT NULL, scanned_at TEXT NOT NULL, PRIMARY KEY (repo, path));
        INSERT INTO skills VALUES ('r', 'a/SKILL.md', 'a', 'd', 'c', '2026-01-01T00:00:00+00:00');
    """)
    conn.close()
    with Store(db) as st:
        assert st.list() == [Skill("r", "a", "d", "c", "a/SKILL.md")]
        dup = Skill("r", "b", "d", "c", "b/SKILL.md", ("x/SKILL.md",))
        st.replace_repo("r", [dup])
        assert st.list() == [dup]


def test_repos_lists_every_scanned_repo_with_counts(tmp_path):
    with Store(tmp_path / "db.sqlite") as st:
        st.replace_repo("r", [Skill("r", "a", "", "c1", "a/SKILL.md"), Skill("r", "b", "", "c1", "b/SKILL.md")])
        st.replace_repo("empty", [], "c2")
        st.conn.execute("UPDATE repos SET scanned_at = '2026-01-01T00:00:00+00:00' WHERE repo = 'r'")
        st.conn.execute("UPDATE repos SET scanned_at = '2026-02-01T00:00:00+00:00' WHERE repo = 'empty'")
        assert st.repos() == [
            RepoEntry("empty", "c2", "2026-02-01T00:00:00+00:00", 0),
            RepoEntry("r", "c1", "2026-01-01T00:00:00+00:00", 2),
        ]
        # a rescan updates the commit and moves the repo to the top
        st.replace_repo("r", [Skill("r", "a", "", "c3", "a/SKILL.md")])
        assert [(e.repo, e.commit, e.skills) for e in st.repos()] == [("r", "c3", 1), ("empty", "c2", 0)]


def test_old_db_backfills_repos(tmp_path):
    import sqlite3

    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE skills (repo TEXT NOT NULL, path TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
                             commit_sha TEXT NOT NULL, duplicates TEXT NOT NULL DEFAULT '[]',
                             scanned_at TEXT NOT NULL, PRIMARY KEY (repo, path));
        INSERT INTO skills VALUES ('r', 'a/SKILL.md', 'a', '', 'c', '[]', '2026-01-01T00:00:00+00:00');
        INSERT INTO skills VALUES ('r', 'b/SKILL.md', 'b', '', 'c', '[]', '2026-01-01T00:00:00+00:00');
    """)
    conn.close()
    with Store(db) as st:
        assert st.repos() == [RepoEntry("r", "c", "2026-01-01T00:00:00+00:00", 2)]
