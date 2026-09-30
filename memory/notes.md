# Notes: discussions without a PR, and standing preferences

## How the user works
- Asks for the spec first (`spec/`), then implementation, then tests for every spec case, then a PR.
- Uses the app's "Create PR" button; PRs are ready for review, not drafts. Accepts Auto-fix on CI.
- Runs several agents in parallel in Docker Sandboxes, each on its own worktree/branch/PR
  (see [PR #5 notes](2026-09-30_1109_feature-web-design.md)).
- Git config has `core.autocrlf=input`; fixture files rely on `tests/fixtures/.gitattributes`.

## Smartphone remote control (2026-09-30, ~10:36 UTC, branch `feature/web-design`, no PR)
- Goal: control this project from the Claude mobile app.
- `claude` CLI wasn't installed: `brew install --cask claude-code`, then `claude auth login`
  (Remote Control needs a claude.ai subscription), then `claude rc` in the project folder.

## Sandbox tooling (2026-09-30, 11:12–12:34 UTC, no PR)
- `scripts/task.sh` and a README line were written but not committed. Details are in
  [PR #5 notes](2026-09-30_1109_feature-web-design.md).
- Hand-made sandboxes `claude-skill-atlas-task-1`/`-task-2` don't follow the script's naming.
