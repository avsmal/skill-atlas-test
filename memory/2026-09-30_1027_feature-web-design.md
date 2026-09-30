# PR #4 — Web UI redesign and catalogue of stored repositories

- **Date/time:** 2026-09-30, discussion started 09:59 UTC, PR opened 10:27 UTC, merged 10:31 UTC
- **Branch:** `feature/web-design`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/4

## What was asked
- Start a new branch; work on the style and design of the web app.
- Add a catalogue of all repositories already in the database.

## What was decided / built
- Home page lists every stored repo (most recent first) with skill count, short commit, scan time.
- `GET /stored?repo=<repo>` shows stored skills without cloning; output equals
  `skill-atlas list --repo <repo> --color never` (shared `output.render_list()`). 404 page offers *Scan it*.
- New `repos` table so 0-skill scans are recorded; backfilled from `skills` on open.
  `Store.replace_repo(repo, skills, commit=None)`.
- Design: top bar, terminal-style output panel (always dark) with the equivalent command and a
  Copy button, light/dark via `prefers-color-scheme`, mobile layout, loading state, `/` focuses input.
- Everything inline, no external requests, no new dependencies; works without JavaScript.
- The "exactly one `<input>` per page" rule was kept here, so no catalogue filter (relaxed in PR #6).
