# Project memory

Decisions and context from past discussions (Claude Code sessions), so new sessions and agents
don't have to rediscover them. The code, `spec/` and git history remain the source of truth;
this folder records *why* and *what was asked*.

- One file per discussion that ended in a pull request:
  `YYYY-MM-DD_HHMM_<branch>.md`, where the time is when the PR was opened (UTC) and `/` in the
  branch name becomes `-`.
- [notes.md](notes.md) holds discussions that didn't produce a PR, plus standing preferences.

| File | PR |
|---|---|
| [2026-09-30_0908_feature-skill-atlas-cli.md](2026-09-30_0908_feature-skill-atlas-cli.md) | #1 CLI: list and store skills |
| [2026-09-30_0935_feature-skill-atlas-cli.md](2026-09-30_0935_feature-skill-atlas-cli.md) | #2 Location rules, edge-case fixture, CI |
| [2026-09-30_0958_feature-skill-atlas-cli.md](2026-09-30_0958_feature-skill-atlas-cli.md) | #3 Web UI, duplicate paths |
| [2026-09-30_1027_feature-web-design.md](2026-09-30_1027_feature-web-design.md) | #4 Web redesign, catalogue |
| [2026-09-30_1109_feature-web-design.md](2026-09-30_1109_feature-web-design.md) | #5 AGENTS.md workflow for parallel agents |
| [2026-09-30_1144_feat-skill-filter.md](2026-09-30_1144_feat-skill-filter.md) | #6 Client-side skill filter |
| [2026-09-30_1152_feat-similar-skills.md](2026-09-30_1152_feat-similar-skills.md) | #7 Similar skills |
| [2026-09-30_1300_ci-python-3.14-only.md](2026-09-30_1300_ci-python-3.14-only.md) | #8 CI on Python 3.14 only |

When a new task ends in a PR, add a file here in the same format.
