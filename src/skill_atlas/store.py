"""SQLite persistence for discovered skills."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import RepoEntry, Skill

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    repo        TEXT NOT NULL,
    path        TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    commit_sha  TEXT NOT NULL,
    duplicates  TEXT NOT NULL DEFAULT '[]',
    content     TEXT NOT NULL DEFAULT '',
    scanned_at  TEXT NOT NULL,
    PRIMARY KEY (repo, path)
);
CREATE TABLE IF NOT EXISTS repos (
    repo        TEXT PRIMARY KEY,
    commit_sha  TEXT NOT NULL,
    scanned_at  TEXT NOT NULL
);
"""
# Fill `repos` for a DB created before the table existed (a no-op afterwards, since
# every repo with skills already has a row). SQLite takes commit_sha from the MAX row.
_BACKFILL_REPOS = """
INSERT OR IGNORE INTO repos (repo, commit_sha, scanned_at)
SELECT repo, commit_sha, MAX(scanned_at) FROM skills GROUP BY repo
"""


def default_db_path() -> Path:
    env = os.environ.get("SKILL_ATLAS_DB")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".skill-atlas" / "atlas.db"


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(_SCHEMA)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(skills)")}
        if "duplicates" not in columns:  # DB created before the column existed
            with self.conn:
                self.conn.execute("ALTER TABLE skills ADD COLUMN duplicates TEXT NOT NULL DEFAULT '[]'")
        if "content" not in columns:  # DB created before the column existed
            with self.conn:
                self.conn.execute("ALTER TABLE skills ADD COLUMN content TEXT NOT NULL DEFAULT ''")
        with self.conn:
            self.conn.execute(_BACKFILL_REPOS)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def replace_repo(self, repo: str, skills: list[Skill], commit: str | None = None) -> None:
        """Replace all stored skills of ``repo`` with ``skills`` atomically.

        ``commit`` is the scanned commit; it defaults to the skills' commit, and must be
        given when ``skills`` is empty so the repo is still recorded in ``repos``.
        """
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if commit is None:
            commit = skills[0].commit if skills else ""
        with self.conn:
            self.conn.execute(
                "INSERT INTO repos (repo, commit_sha, scanned_at) VALUES (?, ?, ?)"
                " ON CONFLICT (repo) DO UPDATE SET commit_sha = excluded.commit_sha,"
                " scanned_at = excluded.scanned_at",
                (repo, commit, now),
            )
            self.conn.execute("DELETE FROM skills WHERE repo = ?", (repo,))
            self.conn.executemany(
                "INSERT INTO skills (repo, path, name, description, commit_sha, duplicates, content, scanned_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        s.repo, s.path, s.name, s.description, s.commit,
                        json.dumps(list(s.duplicates)), s.content, now,
                    )
                    for s in skills
                ],
            )

    def list(self, repo: str | None = None) -> list[Skill]:
        sql = "SELECT repo, name, description, commit_sha, path, duplicates, content FROM skills"
        params: tuple = ()
        if repo:
            sql += " WHERE repo = ?"
            params = (repo,)
        sql += " ORDER BY repo, path"
        return [
            Skill(*row[:5], tuple(json.loads(row[5])), row[6])
            for row in self.conn.execute(sql, params)
        ]

    def repos(self) -> list[RepoEntry]:
        """Every scanned repository with its skill count, most recently scanned first."""
        rows = self.conn.execute(
            "SELECT r.repo, r.commit_sha, r.scanned_at, COUNT(s.path) FROM repos r"
            " LEFT JOIN skills s ON s.repo = r.repo"
            " GROUP BY r.repo ORDER BY r.scanned_at DESC, r.repo"
        )
        return [RepoEntry(*row) for row in rows]
