# PR #10 — Add shared-memory skill for memory/ management

- **Date/time:** 2026-09-30, discussion started 13:25 UTC, PR opened 13:29 UTC
- **Branch:** `docs/shared-memory-skill`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/10

## What was asked
- Create a skill that describes shared memory management.
- Follow-up: all stale records must be removed from the memory.

## What was decided / built
- `.claude/skills/shared-memory/SKILL.md`, the location this project's own spec counts as a skill
  (a single copy; no `.agents` duplicate to keep in sync).
- The skill spells out the `AGENTS.md` › *Shared memory* rules step by step: layout, reading before
  a task, removing stale records, the per-PR file written after `gh pr create` on the same branch,
  a template matching the existing files, rejected-PR feedback via a new branch, and non-PR
  discussions in `notes.md`.
- It includes a shell snippet that builds the file name from `gh pr view --json createdAt`
  (macOS `date -j`, GNU `date -d` fallback); checked against PR #9's file name.
- Stale records: a record is stale when the current code/spec/`main` contradicts it or a later
  decision supersedes it. Stale records are deleted outright (git keeps history), not marked
  outdated. This conflicts with "don't edit other agents' memory files", so removing stale records
  is the one exception. `AGENTS.md` now says so too, since a skill must not contradict it.
  Accurate history ("merged too early, follow-ups in PR #2") is not stale.
- Removals are listed under an optional *Stale records removed* section in the remover's own
  memory file.
- `memory/README.md` and `AGENTS.md` link to the skill.

## Context
- The existing memory was checked against the new rule; no other file had stale records.
- `README.md` edits and `scripts/task.sh` in the working tree are still uncommitted and were left out.
