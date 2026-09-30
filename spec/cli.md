# skill-atlas CLI — Architecture

## Purpose

`skill-atlas` finds the **agent skills** in a GitHub repository and lists them.
Each skill it finds is saved to a local SQLite database as
`(repo, name, description, commit)`, so later runs can query results across repositories.

- **Input:** a GitHub repository (URL or `owner/name`)
- **Output:** the list of skills in that repository, at a specific commit

## Usage

```
$ skill-atlas scan https://github.com/JetBrains/kotlin
https://github.com/JetBrains/kotlin @ c823f9e564fd

1. analysis-api-create-cherry-pick-issue
   description: Create a KTIJ cherry-pick tracking issue for a KT fix that needs to be cherry-picked to an
                IntelliJ branch. Use when cherry-picking Analysis API fixes.
   path:        .claude/skills/analysis-api-create-cherry-pick-issue/SKILL.md

2. analysis-api-mark-internal-apis
   ...

6 skill(s) found
```

### Commands

| Command | Description |
|---|---|
| `skill-atlas scan <repo>` | Clone the repo, find its skills, print them, and save them to the DB |
| `skill-atlas list` | Print the skills saved in the DB |

### Options

| Option | Commands | Meaning |
|---|---|---|
| `--json` | scan, list | Print a JSON array of `{repo, name, description, commit, path}` instead of text |
| `--color WHEN` | scan, list | `auto` (default), `always`, or `never`. See *Output format* |
| `--db PATH` | scan, list | SQLite DB path. Default: `$SKILL_ATLAS_DB`, or `~/.skill-atlas/atlas.db` if unset |
| `--ref REF` | scan | Branch or tag to scan (default: the remote's default branch) |
| `--no-store` | scan | Print only; don't write to the DB |
| `--repo URL` | list | Show only this repository's skills |

Accepted repository forms: `https://github.com/o/r`, `https://github.com/o/r.git`,
`github.com/o/r`, `git@github.com:o/r.git`, `o/r`. All of these normalize to
`https://github.com/o/r`. Any other git URL (e.g. `file://`) is passed to git as is.

## What counts as a skill

Every file named `SKILL.md` (case-insensitive), at any depth in the repository.
That covers `.claude/skills/*/SKILL.md`, `skills/*/SKILL.md`,
`plugins/*/skills/*/SKILL.md`, and similar layouts. The file must start with
YAML frontmatter:

```markdown
---
name: pdf
description: Work with PDF files
---
...instructions...
```

- `name` — taken from the frontmatter. If it's missing, the name of the directory containing the file is used.
- `description` — taken from the frontmatter, with whitespace collapsed to single spaces (so multi-line YAML becomes one line). Empty if missing.
- Files with no frontmatter or invalid frontmatter are skipped, with a `warning:` on stderr.

## Output format

Text output is a numbered list. Each entry takes several lines, with one field per line:

- Line 1: the number, right-aligned to the widest number, then the skill **name**.
- One indented `label: value` line per field, with values aligned in a column:
  - `scan`: `description`, `path`. The repo and commit appear once, in the header line.
  - `list`: `description`, `path`, `repo`, `commit`. Entries can come from several repositories, so each one shows its own.
- Only the description is word-wrapped, to fit the terminal width; continuation lines line up with the value column.
  Paths, URLs and SHAs are never wrapped, so they can be copied.
- Entries are separated by a blank line and followed by a summary line (`N skill(s) found`).

Colors (ANSI SGR):

| Element | Style |
|---|---|
| number | yellow |
| name | bold cyan |
| field labels | dim |
| path | green |
| repo | blue (bold in the header) |
| commit | magenta |
| summary | bold green, or yellow for "No skills found" |
| `warning:` / `error:` prefixes (stderr) | bold yellow / bold red |

`--color auto` turns color on only when all of these hold: the stream is a TTY,
`NO_COLOR` is unset, and `TERM` is not `dumb`. Setting `FORCE_COLOR` turns it on
even without a TTY. stdout and stderr are checked separately. JSON output is never colored.

## Components

```
cli.py ──► repo.py ──► discovery.py ──► parser.py ──► store.py
 (argparse)  (normalize URL,  (walk tree,      (YAML front-   (SQLite
   │          sparse clone,    find SKILL.md)   matter)        persistence)
   │          commit SHA)
   └──► output.py (numbered multi-line rendering, colors)
                        models.Skill (repo, name, description, commit, path)
```

| Module | Responsibility |
|---|---|
| `cli.py` | Parses arguments, runs `scan`/`list`, prints JSON, sets exit codes |
| `output.py` | `use_color()`, `Painter` (ANSI styling), `render_skills()` / `render_header()` / `render_summary()`, and the `warn()` / `error()` stderr helpers |
| `repo.py` | `normalize_repo_url()`. `clone()` is a context manager that clones into a temp dir, yields `(path, commit_sha)`, and deletes the temp dir afterwards |
| `discovery.py` | `find_skill_files(root)`: sorted list of `SKILL.md` paths, skipping `.git` and `node_modules` |
| `parser.py` | `parse_frontmatter()` and `parse_skill()` → `(name, description)`. Raises `SkillParseError` on bad input |
| `models.py` | The `Skill` dataclass |
| `store.py` | The `Store` class: creates the schema, `replace_repo()`, `list()` |

### Fetching strategy

The repository is cloned so that only skill files are downloaded:

1. `git clone --depth 1 --filter=blob:none --no-checkout [--branch REF] <url>` fetches one commit and its trees, but no file contents.
2. `git sparse-checkout set --no-cone '[Ss][Kk][Ii][Ll][Ll].[Mm][Dd]'` limits the checkout to files named `SKILL.md`.
3. `git checkout` downloads only those files.
4. `git rev-parse HEAD` gives the commit that was scanned.

This keeps huge repositories cheap to scan: `JetBrains/kotlin` takes about 5 s instead of
downloading the full tree. Git LFS filters are disabled (`GIT_LFS_SKIP_SMUDGE=1`
plus `-c filter.lfs.*=` overrides), so git-lfs does not need to be installed.
`GIT_TERMINAL_PROMPT=0` makes clones of private or missing repositories fail
immediately instead of stopping to ask for a password.

## Data model

SQLite, one table:

```sql
CREATE TABLE skills (
    repo        TEXT NOT NULL,   -- normalized URL
    path        TEXT NOT NULL,   -- SKILL.md path relative to the repo root
    name        TEXT NOT NULL,
    description TEXT,
    commit_sha  TEXT NOT NULL,   -- full 40-char SHA that was scanned
    scanned_at  TEXT NOT NULL,   -- ISO-8601 UTC
    PRIMARY KEY (repo, path)
);
```

The key is `(repo, path)` rather than `(repo, name)`, because two skills in one repository can share a name.
A scan replaces **all** rows for its repository in a single transaction. Rescanning
never creates duplicates, and skills that were deleted upstream disappear from the DB.

## Errors and exit codes

| Situation | Behavior |
|---|---|
| Success, including 0 skills found | exit 0; prints "No skills found" when there are none |
| git missing, clone fails, or the repo/ref doesn't exist | `error: <git stderr>` on stderr, exit 1, DB unchanged |
| Malformed `SKILL.md` | `warning: skipping <path>: <reason>` on stderr; the scan continues |
| Bad CLI arguments | argparse usage message, exit 2 |

## Testing

`pytest` covers:
- the parser, discovery, and URL normalization (unit tests)
- output: color decisions, number alignment, description wrapping
- the store: replace semantics and filtering
- end-to-end `scan` and `list` against a local git fixture repo, cloned through a `file://` URL (no network)

## Future work

- A GitHub API backend (Trees API + raw content) for environments without git.
- Private repositories via `GITHUB_TOKEN`.
- Skipping a rescan when the remote HEAD is unchanged (`git ls-remote` against the stored `commit_sha`).
- Other skill formats (e.g. `AGENTS.md`, Cursor rules) and extra frontmatter fields (`license`, `allowed-tools`).
