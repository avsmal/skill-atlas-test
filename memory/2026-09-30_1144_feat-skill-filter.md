# PR #6 — Web UI: client-side skill filter

- **Date/time:** 2026-09-30, PR opened 11:44 UTC, merged 12:45 UTC
- **Branch:** `feat/skill-filter`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/6
- **Source:** done by a parallel agent in a Docker Sandbox; its transcript isn't stored locally, so this
  is reconstructed from the PR.

## What was decided / built
- A JS-only search box on scan-result and stored-repo output panels filters the numbered list by
  name/description (case-insensitive substring), without a server round-trip.
- `render_skills()`/`render_list()` got an optional `wrap(skill, block)` hook so the web layer adds
  `data-name`/`data-desc` without changing the CLI's plain text.
- `spec/web.md`: the "exactly one `<input>`" invariant is relaxed for pages whose output lists at
  least one skill.
