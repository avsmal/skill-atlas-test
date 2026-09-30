# skill-atlas

A CLI that lists a GitHub repository's own agent skills (`SKILL.md` files under
`.agents/skills/` and `.claude/skills/`) and saves them (repo, name, description, commit) to a local SQLite database.

```bash
pip install -e .
skill-atlas scan https://github.com/JetBrains/kotlin
skill-atlas scan JetBrains/kotlin --json
skill-atlas list --color never   # auto | always | never
```

See [spec/cli.md](spec/cli.md) for the architecture and the exact rules for what counts as a skill
(excluded folders, `.agents`/`.claude` de-duplication). Run the tests with `pip install -e '.[dev]' && pytest`.
