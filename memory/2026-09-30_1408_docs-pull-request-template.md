# PR #12 — Add pull request template

- **Date/time:** 2026-09-30, PR opened 14:08 UTC
- **Branch:** `docs/pull-request-template`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/12

## What was asked
- Create `.github/pull_request_template.md`.
- Follow-up: also cover known issues and the parts that can break easily.
- Follow-up: mention the template in `AGENTS.md`.

## What was decided / built
- Sections: *What and why*, *Spec*, *Tests*, *Known issues and fragile parts* (still broken or
  deferred; what breaks easily and how it would show; "none known" instead of deleting it), and a checklist mirroring `AGENTS.md` ›
  *Definition of done* (branch from `origin/main`, spec updated, integration tests, local tests,
  green CI, memory file, stale memory removed). Comments in the sections say what to write.
- `gh pr create --fill` ignores the template, so `AGENTS.md` now says to open PRs with
  `--title` and a `--body-file` following the template.
- `AGENTS.md` › *Workflow* has a bullet to fill every template section ("none known" allowed) and keep
  the description current; *Definition of done* requires the description to follow the template.
- No spec change: repository process only.
