# PR #19 — Web UI: let people star skills

- **Date/time:** 2026-10-01, discussion started ~08:20 UTC, PR opened 08:44 UTC
- **Branch:** `feat/star-skills`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/19

## What was asked
- "Let people star skills" (one line, no further detail; the agent chose the design below).

## What was decided / built
- **Anonymous visitors, not accounts.** There is no login, so a "person" is a random id in an
  `HttpOnly`/`SameSite=Lax` cookie set by the first star (never by viewing a page). This gives one
  star per person per skill without adding auth. Accepted trade-off: stars are a signal, not a vote
  (clearing cookies adds stars); written into the spec and the PR's known issues.
- **`stars` table keyed `(repo, path, visitor)`, no FK to `skills`.** `replace_repo()` deletes and re-inserts
  a repo's skills on every scan, so stars tied to `skills` rows would vanish on rescan. Skills deleted
  upstream are hidden (joined away) and get their stars back if they return.
- **Buttons inside the `<pre>` add no text.** The "`<pre>` text equals the CLI" rule (and Copy) must hold,
  so the button is empty and CSS draws `☆ N` from `data-stars`. `render_skills()`/`render_list()` got a
  `name_suffix(skill)` hook for it, next to `name_url`/`wrap`.
- **No new `<input>`.** Buttons point at one empty hidden `<form id="star-form">` via `form=` + `formaction`
  (all parameters in the query string), keeping the "one repository input" invariant.
- **No-JS first, JS in place.** `POST /star` → `303` to `next` (local paths only). JS posts the same URL with
  `Accept: application/json` and updates the button without a reload, so long lists keep their scroll.
  From a scan result, `next` is the stored page: returning to `/?repo=` would clone again.
- **CSRF:** `POST /star` with an `Origin` for another host → `403`. `--no-store` still saves stars (they aren't scan results).
- Home gets **Most starred** (top 10) only when something is starred, so the empty-DB demo frames
  (`01-home-empty`, `05-catalogue`) don't change.

## Context
- PyPI downloads (`files.pythonhosted.org`) are blocked in this sandbox; only the index and github.com
  are reachable. pytest, pluggy, iniconfig, packaging, pygments and pure-Python PyYAML were cloned from
  GitHub onto `PYTHONPATH` (pytest/pluggy/iniconfig need a hand-written `_version.py`). Pillow couldn't be
  made to work from Ubuntu pool debs (library version mismatch), so `tests/test_demo_video.py` ran only in CI.
- No browser in the sandbox: the page JS was checked with `node --check` plus a stubbed-DOM run. The
  rendered buttons were never seen by the agent (see the next point), so check them in the new frames.
- The first CI run (36838238671) passed `pytest` on both OSes. `demo-video` failed on exactly the 5 frames
  that film the new star buttons (`02`, `03`, `04`, `06`, `07`); `01`, `05` and `08` were pixel-identical.
  The baseline couldn't be replaced from the sandbox: `gh run download` fetches from
  `*.blob.core.windows.net`, which the sandbox proxy blocks. It needs `scripts/demo/update-baseline.sh
  <run id>` run from a machine that can download artifacts.
