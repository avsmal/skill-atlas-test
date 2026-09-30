# PR #2 — Skill location rules, edge-case fixture tests, GitHub CI

- **Date/time:** 2026-09-30, discussion 09:10–09:36 UTC, PR opened 09:35 UTC, merged 09:37 UTC
- **Branch:** `feature/skill-atlas-cli` (follow-up to PR #1, which was merged too early)
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/2

## What was asked
- Tests for edge cases (duplicate skills in different folders, unusual folders, …).
- Put the edge-case rules into the spec:
  1. Duplicate skills in `.agents` and `.claude` folders.
  2. Ignore skills that are the project's own workflow outside `.agents`/`.claude`.
  3. Ignore skills shipped to users inside plugins (e.g. `resources` folders).
  4. Ignore skills in the project's own tests.
- Implement, then test edge cases with a local fixture repo.
- Run tests in GitHub CI; add `AGENTS.md` with the user's text; turn on CI Auto-fix.

## What was decided / built
- Only `<prefix>/.agents/skills/<dir>/SKILL.md` and `<prefix>/.claude/skills/<dir>/SKILL.md` count.
  Resource, test, vendored and build folders are excluded. `.agents`/`.claude` copies are merged,
  preferring `.agents` (`dedupe.py`), with a warning if they differ. Symlinked `SKILL.md` is skipped.
- `tests/fixtures/edge-repo/` + `edge-repo.expected.json` hold every spec case;
  `tests/fixtures/.gitattributes` (`-text`) keeps CRLF/BOM files byte-exact (the user's global
  `core.autocrlf=input` would otherwise rewrite them).
- YAML errors are reported on one line.
- CI: `.github/workflows/tests.yml` (then Ubuntu py3.10–3.14 + macOS py3.14; see PR #8).
- Consequence: `anthropics/skills` now reports 0 skills (its skills live in `skills/`), as intended.
  JetBrains/kotlin reports 6.

## Context
- `AGENTS.md` was committed exactly as written, including `./specs/` (fixed in PR #5) and
  "every cast" (presumably "case").
