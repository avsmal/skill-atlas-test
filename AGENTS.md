# AGENTS.md
## Specs
Read ./spec/ first. Update it with the code.
## Tests
Integration tests for every case in the spec.
## Workflow
- One task = one branch = one PR. Before any change: `git switch -c <type>/<short-task-name> origin/main`.
- Setup in a fresh clone/sandbox: `python -m venv .venv && . .venv/bin/activate && python -m pip install -e '.[dev]'`.
- Other agents work on this repo in parallel: never push to `main` or to a branch you did not create.
- If `git push` over SSH fails, switch to HTTPS: `git remote set-url origin https://github.com/avsmal/skill-atlas-test.git && gh auth setup-git`.
- PR description: copy `.github/pull_request_template.md` and fill in every section, including *Known issues and fragile parts* ("none known" if so); keep it current as you push more commits.
- Open the PR with `gh pr create --base main --title "<title>" --body-file <file>` (`--fill` and `--body` skip the template).
## Definition of done
- All tests pass locally
- Pushed, PR open against `main`, description follows `.github/pull_request_template.md`
- CI is green for this commit (`gh pr checks --watch`)
- Red CI: read the logs (`gh run view --log-failed`), fix, push again
- Memory file for this PR is committed
## Shared memory
- Read `memory/` before starting a task.
- After opening the PR, add `memory/YYYY-MM-DD_HHMM_<branch>.md` (PR open time in UTC, `/` in the branch → `-`) to the same branch and push: what was asked, what was decided, and why. Don't edit other agents' memory files, except to remove stale records.
- Remove every stale record (contradicted by the current code/spec or superseded by a later decision) from `memory/`, including ones your change makes stale.
- Step-by-step guide: `.claude/skills/shared-memory/SKILL.md`.
- If a PR is rejected or gets review feedback, record the problem and the lesson in `memory/` in a new branch and PR (a rejected branch never reaches `main`).
