# skill-atlas

[![tests](https://github.com/avsmal/skill-atlas-test/actions/workflows/tests.yml/badge.svg)](https://github.com/avsmal/skill-atlas-test/actions/workflows/tests.yml)

A CLI that lists a GitHub repository's own agent skills (`SKILL.md` files under
`.agents/skills/` and `.claude/skills/`) and saves them (repo, name, description, commit) to a local SQLite database.

```bash
pip install -e .
skill-atlas scan https://github.com/JetBrains/kotlin
skill-atlas scan JetBrains/kotlin --json
skill-atlas list --color never   # auto | always | never
skill-atlas serve                # web UI on http://127.0.0.1:8000/
```

See [spec/cli.md](spec/cli.md) for the architecture and the exact rules for what counts as a skill
(excluded folders, `.agents`/`.claude` de-duplication), and [spec/web.md](spec/web.md) for the web UI. Run the tests with `pip install -e '.[dev]' && pytest`.
