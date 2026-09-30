# PR #13 — docs: web UI demo video script

- **Date/time:** 2026-09-30, discussion started ~14:15 UTC, PR opened 14:31 UTC
- **Branch:** `docs/web-demo-script`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/13

## What was asked
- Write the script for a video demo of the web interface before recording it.
- Script lives in the repo (branch + PR); ~3 min, for general developers; dry-run it live first.
- Use JetBrains/ideavim as an example (added while reviewing the plan).

## What was decided / built
- `docs/demo-script.md`: 8 scenes (hook, scan, GitHub links + shareable URL, filter, more repos via
  `/`, catalogue + stored page, Similar skills, theme/mobile + outro), each with on-screen action
  and voice-over. Linked from README.
- ideavim leads (6 skills, fast clone ~2 s); kotlin (6) and skill-atlas-test (1) fill the catalogue.
  Scene 7 uses ideavim's `extensions-api-migration`, whose top similar skill (18.8 %) is in kotlin —
  the only ideavim skill whose best match is in another repo, which is the point of the scene.
- Real numbers are pinned to the dry-run commits; a Fallbacks section explains how to refresh them.
- Recording uses a fresh `--db` so the catalogue starts empty.
