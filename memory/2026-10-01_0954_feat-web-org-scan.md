# PR #21 — web: scan organizations and users (streamed, cancellable)

- **Date/time:** 2026-10-01, discussion started ~09:25 UTC, PR opened 09:54 UTC
- **Branch:** `feat/web-org-scan`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/21

## What was asked
- Scanning `https://github.com/JetBrains` in the web UI gave `error: organizations can only be scanned from
  the CLI: …` (the 400 added in [PR #20](2026-10-01_0902_feat-org-scan.md)). Make it work in the web UI.

## What was decided / built
- PR #20 blocked it because one page load clones hundreds of repos. That's handled by **streaming** the page,
  not by a background job with polling. Streaming keeps "the same output as the CLI" as one URL, needs no job
  state or new endpoints, and gives cancellation for free: a failed write means the visitor left.
  A job queue was rejected as more state for the same result.
- HTTP/1.0 without `Content-Length` (the stdlib handler's default protocol), so the body ends at close.
  The status is fixed before streaming: `200` once the repo list is fetched, `502` (not streamed) if
  listing fails. Per-repository clone failures are `error:` lines, as in the CLI.
- Progress without JS: an empty `<i class="tick" data-done data-total>` after each repo, and CSS
  `:last-of-type` + `attr()` draws it. The ticks also make sure there's a write after every repo, which
  is how a disconnect gets noticed even when no repo has skills.
- The CLI loop became `cli.scan_owner_repos()` (shared). It wraps `pool.map()` in `closing()` because
  a generator closed at its `yield` doesn't close the inner map iterator before `with ThreadPoolExecutor`
  calls `shutdown(wait=True)`, which would otherwise clone the whole queue after the visitor left.
- On owner pages the filter field is always emitted (hidden), and the JS unhides it only if a `.skill` exists,
  because the page head is sent before any skill is known. Star buttons use global star counts loaded
  once, with `next` set to each skill's own stored page.
- No `--include-forks`/`--jobs` in the web UI (forks skipped, 4 jobs). No home-page text was changed, so the
  demo-video screenshots stay the same.

## Context
- Sandbox: pip is still blocked by the proxy. Tests ran on Python 3.12 with shallow GitHub clones of
  pytest, pluggy, iniconfig, packaging, pygments and pyyaml on `PYTHONPATH` (hand-written `_version.py`
  files), as in PR #20.
- Live: `anthropics` via the web UI took ~14 s for 88 repos (`30 skill(s) found in 9 of 88 repositories`).
  No browser in the sandbox, so the CSS progress line wasn't seen rendered.

## Stale records removed
- `2026-10-01_0902_feat-org-scan.md`: the bullet saying the web UI refuses owner URLs with a 400 and lists
  web org scans under *Future work*. This PR implements them.
