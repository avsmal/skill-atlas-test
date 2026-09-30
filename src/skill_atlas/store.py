"""SQLite persistence for discovered skills."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Skill

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    repo        TEXT NOT NULL,
    path        TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    commit_sha  TEXT NOT NULL,
    duplicates  TEXT NOT NULL DEFAULT '[]',
    scanned_at  TEXT NOT NULL,
    PRIMARY KEY (repo, path)
);
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

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def replace_repo(self, repo: str, skills: list[Skill]) -> None:
        """Replace all stored skills of ``repo`` with ``skills`` atomically."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute("DELETE FROM skills WHERE repo = ?", (repo,))
            self.conn.executemany(
                "INSERT INTO skills (repo, path, name, description, commit_sha, duplicates, scanned_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (s.repo, s.path, s.name, s.description, s.commit, json.dumps(list(s.duplicates)), now)
                    for s in skills
                ],
            )

    def list(self, repo: str | None = None) -> list[Skill]:
        sql = "SELECT repo, name, description, commit_sha, path, duplicates FROM skills"
        params: tuple = ()
        if repo:
            sql += " WHERE repo = ?"
            params = (repo,)
        sql += " ORDER BY repo, path"
        return [
            Skill(*row[:5], tuple(json.loads(row[5])))
            for row in self.conn.execute(sql, params)
        ]
