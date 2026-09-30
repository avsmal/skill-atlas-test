# PR #18 — Web UI: dark-green page background

- **Date/time:** 2026-09-30, discussion started ~16:15 UTC, PR opened 16:29 UTC
- **Branch:** `style/dark-green-background`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/18

## What was asked
- Change the background of the web page to dark green.

## What was decided / built
- One dark-green palette for every system theme (`--bg: #0f2a1d`, light text, green-tinted surfaces,
  mint accent `#6fd39a`, `color-scheme: dark`); the `prefers-color-scheme` light/dark split was removed.
  Why: most text (hero, catalogue, notes) sits directly on the page background, so a dark-green
  background under the light theme's dark text would be unreadable; keeping a light theme with a
  green background would need per-element text colours and was judged fragile.
- Accent switched from indigo to mint so buttons/badges/links suit the green.
- Output panel keeps its neutral dark terminal palette (CLI colours unchanged).
- Spec `web.md` › *Design* and *Testing* updated; `docs/demo-script.md` outro no longer switches to light theme.

## Context
- `docs/demo.mp4`/GIF/screenshots still show the old palette; re-record with the `record-demo` skill if wanted.

## Stale records removed
- `2026-09-30_1027_feature-web-design.md`: "light/dark via `prefers-color-scheme`" — themes no longer follow the system.
- `2026-09-30_1431_docs-web-demo-script.md`: "theme/" in scene 8 — the script no longer has a theme switch.
