# PR #1 — skill-atlas CLI: list and store agent skills from a GitHub repo

- **Date/time:** 2026-09-30, discussion started 08:36 UTC, PR opened 09:08 UTC, merged 09:09 UTC
- **Branch:** `feature/skill-atlas-cli`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/1

## What was asked
- Develop the `skill-atlas` CLI in Python. Input: a GitHub repository; output: the list of skills
  in it (`skill-atlas scan https://github.com/JetBrains/kotlin`).
- Write the architecture to `spec/cli.md`.
- Store repo, name, description and commit.
- Follow-up: colored output, numbered skills, each entry multi-line with one field per line.

## What was decided / built
- `scan` sparse-clones only `SKILL.md` files, parses the YAML front matter (`name`,
  `description`), and saves to SQLite at `~/.skill-atlas/atlas.db` (`--db`, `$SKILL_ATLAS_DB`).
  Rescanning a repo replaces its rows.
- `list [--repo URL]` shows stored skills. `--color auto|always|never`, `NO_COLOR`, `--json`.
- Git LFS is disabled during the clone: without that, scanning failed on machines lacking `git-lfs`.
- At this point any `SKILL.md` at any depth counted as a skill (narrowed in PR #2).

## Context
- The local machine initially had no `pip` or `gh` on PATH; use `.venv/bin/...` and `gh` was
  installed and authenticated during this session.
- The PR was merged while more commits were still being pushed to its branch; those landed via PR #2.
