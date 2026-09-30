---
name: shared-memory
description: Read and write the repo's shared memory in memory/ (decisions and context shared by all agents working on this project). Use at the start of every task to catch up, after opening a PR to add its memory file, when a PR is rejected or gets review feedback, and when a discussion ends without a PR.
---

# Shared memory (`memory/`)

Several agents work on this repo in parallel, each on its own branch and PR. `memory/` is how
they share *what was asked, what was decided, and why*. The code, `spec/` and git history stay
the source of truth; memory records the reasoning that isn't visible there.

## Layout

- `memory/YYYY-MM-DD_HHMM_<branch>.md`: one file per PR. Time = when the PR was opened, in UTC.
  `/` in the branch name becomes `-` (branch `feat/similar-skills` → `..._feat-similar-skills.md`).
- `memory/notes.md`: discussions that ended without a PR, and standing preferences of the user.
- `memory/README.md`: explains the folder. **No index table**: the sorted folder listing is the
  index, so parallel PRs don't all edit the same file and conflict.

## 1. Before starting a task: read

```bash
ls memory/                      # sorted by time = chronological
cat memory/notes.md             # how the user works
```

Then read the files whose branch names relate to the task, plus the latest few. Treat them as
background: if a memory names a file, flag or function, check it still exists before relying on it.

## 2. After `gh pr create`: add the PR's memory file

The file name needs the PR open time, so it's written after the PR exists, on the **same branch**:

```bash
branch=$(git branch --show-current)
created=$(gh pr view --json createdAt -q .createdAt)          # e.g. 2026-09-30T13:17:31Z
file="memory/$(date -u -j -f %Y-%m-%dT%H:%M:%SZ "$created" +%Y-%m-%d_%H%M 2>/dev/null \
  || date -u -d "$created" +%Y-%m-%d_%H%M)_${branch//\//-}.md"
echo "$file"
```

Template (match the existing files):

```markdown
# PR #<n> — <PR title>

- **Date/time:** YYYY-MM-DD, discussion started HH:MM UTC, PR opened HH:MM UTC
- **Branch:** `<branch>`
- **PR:** <PR URL>

## What was asked
- The user's requests, in order, including follow-ups and corrections.

## What was decided / built
- Decisions and the reason for each; alternatives rejected and why.
- Behaviour changes users would notice; spec sections touched.

## Context
- Optional: environment quirks, surprises, things the next agent would otherwise rediscover.
```

Commit it (`git add memory/<file>`), push, and wait for CI again: the memory file is part of the
definition of done. Only stage your own file; other uncommitted changes in the tree are not yours.

## 3. Rules

- **Don't edit other agents' memory files.** If one is wrong or outdated, say so in your own file
  (link it with a relative link, e.g. `[PR #5 notes](2026-09-30_1109_feature-web-design.md)`).
- `memory/notes.md` is shared: append a dated section, don't rewrite others' sections.
- Keep it short and factual. No secrets, tokens or personal data.
- Don't duplicate what the diff, spec or commit messages already say; record the *why*.
- More pushes to the same PR after the file exists (e.g. follow-up requests): update your own
  file in the same branch.

## 4. PR rejected or review feedback

A rejected branch never reaches `main`, so its memory file would be lost. Record the lesson on a
**new** branch and PR from `origin/main`:

```bash
git switch -c docs/memory-<short-topic> origin/main
```

Add `memory/YYYY-MM-DD_HHMM_<new-branch>.md` (as in step 2, for the new PR) with: the original
PR link, what the feedback or rejection was, the lesson, and how to apply it next time. If the
lesson is a standing preference, also add it to `memory/notes.md`.

## 5. Discussion without a PR

Add a dated section to `memory/notes.md` (topic, time in UTC, branch if any, what was concluded)
and commit it with the next PR you open, or on its own `docs/memory-<topic>` branch.
