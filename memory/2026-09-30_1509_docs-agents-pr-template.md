# PR #15 — AGENTS.md: require PR descriptions to follow the template

- **Date/time:** 2026-09-30, PR opened 15:09 UTC
- **Branch:** `docs/agents-pr-template`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/15

## What was asked
- Mention the PR template (added in [PR #12](2026-09-30_1408_docs-pull-request-template.md)) in `AGENTS.md`.

## What was decided / built
- `AGENTS.md` › *Workflow*: copy the template, fill in every section (\"none known\" allowed for
  *Known issues and fragile parts*), keep the description current as more commits are pushed.
- *Definition of done*: the PR description follows the template.

## Context
- This was first pushed to PR #12's branch, but PR #12 had been merged at 14:19 UTC, a minute
  before; pushes to a merged PR's branch never reach `main`. Check `gh pr view --json state`
  before pushing a follow-up to an existing PR branch.
