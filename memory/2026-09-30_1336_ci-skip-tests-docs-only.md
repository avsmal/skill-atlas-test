# PR #11 — CI: skip tests when only Markdown changed

- **Date/time:** 2026-09-30, discussion started 13:33 UTC, PR opened 13:36 UTC
- **Branch:** `ci/skip-tests-docs-only`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/11

## What was asked
- Run the CI tests only when code files changed; no tests if only `.md` files changed.

## What was decided / built
- A `changes` job in `.github/workflows/tests.yml` diffs against the PR merge-base (or the
  push's `before`); `pytest` has `needs: changes` + `if:`. Job-level skip instead of
  workflow-level `paths-ignore`: a skipped job reports as passing, so docs-only PRs still get a
  check and `gh pr checks --watch` (definition of done) doesn't fail with "no checks".
- Plain `git diff` in a shell step instead of `dorny/paths-filter`: no third-party action, and the
  "Markdown, except under `tests/`" rule is awkward to express in its globs.
- `*.md` under `tests/` is fixture data (`SKILL.md` files), so it still runs the tests.
- Manual runs, new branches (`before` = zeros) and unknown bases always run the tests.
- `spec/cli.md` → Continuous integration updated.

## Context
- `gh`'s HTTPS token lacks the `workflow` scope, so pushes that change `.github/workflows/` are
  rejected over HTTPS; push those over SSH (`git@github.com:avsmal/skill-atlas-test.git`).
- `main` has no branch protection (no required checks), checked via the GitHub API.
