# AGENTS.md
## Specs
Read ./spec/ first. Update it with the code.
## Tests
Integrations test for every cast in the spec.
## Workflow
- One task = one branch = one PR. Before any change: `git switch -c <type>/<short-task-name> origin/main`.
- Setup in a fresh clone/sandbox: `python -m venv .venv && . .venv/bin/activate && python -m pip install -e '.[dev]'`.
- Other agents work on this repo in parallel: never push to `main` or to a branch you did not create.
- If `git push` over SSH fails, switch to HTTPS: `git remote set-url origin https://github.com/avsmal/skill-atlas-test.git && gh auth setup-git`.
- Open the PR with `gh pr create --base main --fill` (or a written title/body).
## Definition of done
- All tests pass locally
- Pushed, PR open against `main`
- CI is green for this commit (`gh pr checks --watch`)
- Red CI: read the logs (`gh run view --log-failed`), fix, push again
