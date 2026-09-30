# PR #10 — Add shared-memory skill for memory/ management

- **Date/time:** 2026-09-30, discussion started 13:25 UTC, PR opened 13:29 UTC
- **Branch:** `docs/shared-memory-skill`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/10

## What was asked
- Create a skill that describes shared memory management.

## What was decided / built
- `.claude/skills/shared-memory/SKILL.md`, the location this project's own spec counts as a skill
  (a single copy; no `.agents` duplicate to keep in sync).
- The skill spells out the `AGENTS.md` › *Shared memory* rules step by step: layout, reading before
  a task, the per-PR file written after `gh pr create` on the same branch, a template matching the
  existing files, not editing other agents' files, rejected-PR feedback via a new branch, and
  non-PR discussions in `notes.md`.
- It includes a shell snippet that builds the file name from `gh pr view --json createdAt`
  (macOS `date -j`, GNU `date -d` fallback); checked against PR #9's file name.
- `memory/README.md` links to the skill; `AGENTS.md` is unchanged (it stays the short rule set).

## Context
- `README.md` edits and `scripts/task.sh` in the working tree are still uncommitted and were left out.
