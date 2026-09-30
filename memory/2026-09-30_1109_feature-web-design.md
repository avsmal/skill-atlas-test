# PR #5 — AGENTS.md: workflow for parallel sandboxed agents

- **Date/time:** 2026-09-30, discussion started 10:55 UTC, PR opened 11:09 UTC, merged 11:10 UTC
- **Branch:** `feature/web-design` (reused; the PR contained only the AGENTS.md/CLAUDE.md commit)
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/5

## What was asked
- Run Claude Code in Docker Sandboxes (`sbx`) and work on the project in parallel with git worktrees.
- Agents must work in parallel and each open their own pull request.
- Commit the new `AGENTS.md` and `CLAUDE.md`.

## What was decided / built
- `AGENTS.md`: spec path fixed to `./spec/`; *Workflow* section (one task = one branch = one PR from
  `origin/main`; venv setup; never push to `main` or another agent's branch; SSH→HTTPS fallback via
  `gh auth setup-git`); *Definition of done* includes PR open and green CI.
- `CLAUDE.md` is just `@AGENTS.md`.
- GitHub token for sandboxes: `sbx secret set github --command 'gh auth token'` (kept on the host,
  injected on the way out).
- Suggested (not done): branch protection on `main` for a hard guarantee.

## Follow-ups in the same session (no PR yet)
- Starting a task on a worktree: mount the worktree **and** the main repo's `.git`
  (`sbx run --name <t> claude ../skill-atlas-<t> "$PWD/.git"`), since a worktree's `.git` is only a pointer.
- Claude login in sandboxes: `claude setup-token`, store in Keychain as `claude-oauth-token`, pass as
  `CLAUDE_CODE_OAUTH_TOKEN` (visible to the agent). Alternative: `sbx secret set anthropic` (API billing).
- `scripts/task.sh <name> [base]` / `scripts/task.sh rm <name>` automates worktree + branch
  (`feat/<slug>`) + sandbox (`skill-atlas-<slug>`) + token. Written and tested with the `shell` agent;
  left uncommitted along with a README line.
- Reaching a web app in a sandbox: run `skill-atlas serve --host 0.0.0.0`, then
  `sbx ports <sandbox> --publish 8000` and open `http://127.0.0.1:<port>/`. Not verified end to end.
