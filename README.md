# skill-atlas

A CLI that lists the agent skills (`SKILL.md` files) in a GitHub repository and saves
them (repo, name, description, commit) to a local SQLite database.

```bash
pip install -e .
skill-atlas scan https://github.com/JetBrains/kotlin
skill-atlas scan anthropics/skills --json
skill-atlas list --color never   # auto | always | never
```

See [spec/cli.md](spec/cli.md) for the architecture. Run the tests with `pip install -e '.[dev]' && pytest`.
