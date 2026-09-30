# PR #7 — "Similar skills" in the web UI

- **Date/time:** 2026-09-30, PR opened 11:52 UTC, merged 12:59 UTC
- **Branch:** `feat/similar-skills`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/7
- **Source:** done by a parallel agent in a Docker Sandbox; its transcript isn't stored locally, so this
  is reconstructed from the PR.

## What was decided / built
- Each skill on `/stored?repo=` has a **Similar skills** link, later merged into the main skills list.
- `GET /similar?repo=<repo>&path=<path>` lists other stored skills more than 10% similar, most
  similar first.
- Similarity = mean of `difflib.SequenceMatcher.ratio()` over `description` and `content`
  (the `SKILL.md` body, now parsed, stored in the DB and included in `--json`), so no re-clone is needed.
- The branch was merged with `origin/main` after PR #6 landed.
