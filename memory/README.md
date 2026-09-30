# Project memory

Decisions and context from past discussions (Claude Code sessions), so new sessions and agents
don't have to rediscover them. The code, `spec/` and git history remain the source of truth;
this folder records *why* and *what was asked*.

- One file per discussion that ended in a pull request:
  `YYYY-MM-DD_HHMM_<branch>.md`, where the time is when the PR was opened (UTC) and `/` in the
  branch name becomes `-`.
- [notes.md](notes.md) holds discussions that didn't produce a PR, plus standing preferences.

The folder listing is the index (sorted by time); there is deliberately no table here, so
parallel PRs don't conflict.

When a new task ends in a PR, add a file here in the same format (see `AGENTS.md` › *Shared memory*).
