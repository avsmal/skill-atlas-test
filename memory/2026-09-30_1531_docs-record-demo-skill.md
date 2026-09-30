# PR #16 — Add record-demo skill: scripted web UI demo videos

- **Date/time:** 2026-09-30, discussion started ~15:15 UTC, PR opened 15:31 UTC
- **Branch:** `docs/record-demo-skill`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/16

## What was asked
- Turn the session that produced the demo video ([PR #13](2026-09-30_1431_docs-web-demo-script.md),
  [PR #14](2026-09-30_1450_docs-demo-video.md)) into a skill for recording demo videos.

## What was decided / built
- Project skill `.claude/skills/record-demo/`: `SKILL.md` (workflow + pitfalls), `scripts/demo_kit.py`
  (reusable `Demo` recorder), `scripts/demo_30s.py` (the scenes of `docs/demo.mp4`).
- Scenes are plain Python on top of the kit, not a config format: a new cut is a copied scenes file,
  and Playwright locators stay available for anything the helpers don't cover.
- The kit does the post-processing on exit (trimmed MP4, GIF preview, frame sheet), so the
  "check the frame sheet before showing the video" step can't be skipped for lack of a file.

## Stale records removed
- `2026-09-30_1450_docs-demo-video.md`: "The recording scripts were not committed" — they are now,
  as this skill.
