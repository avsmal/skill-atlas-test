# PR #14 — docs: 30-second web UI demo video

- **Date/time:** 2026-09-30, discussion started ~14:38 UTC, PR opened 14:50 UTC
- **Branch:** `docs/demo-video`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/14

## What was asked
- Record the demo from [PR #13's script](2026-09-30_1431_docs-web-demo-script.md); then make it a
  short ~30 s video instead of the 3-minute version; then commit the video to the repo.
- A request to add JetBrains/MPS and JetBrains/intellij-community examples was withdrawn.

## What was decided / built
- `docs/demo.mp4`: silent (voice-over can't be recorded by the agent), 32 s, 1280×800, dark theme.
  Scenes: scan ideavim → filter `commit` → scan kotlin → catalogue → stored ideavim → Similar to
  `extensions-api-migration` → install card.
- Recorded with Playwright (user approved the download) rather than macOS screen capture, so only
  the page is filmed. Playwright doesn't render the mouse, so a fake cursor is injected. Scan waits
  are cut with ffmpeg, leaving 0.8 s of *Scanning…*. The recording scripts were not committed.

## Context
- Clone times vary a lot: kotlin took 4 s once and 20–34 s later.
- Something else was listening on port 8000 on the user's machine; the recording used 8766.
- MPS (41 skills) and intellij-community (38 skills, plus 38 `.agents`/`.claude` "copies differ"
  warnings) both scan fine; they share skill names `registry` and `ssr` — a candidate
  cross-repo *Similar skills* example if wanted later (scores not computed).
