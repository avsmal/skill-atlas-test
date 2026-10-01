# skill-atlas CLI — Architecture

## Purpose

`skill-atlas` finds the **agent skills** in a GitHub repository and lists them.
Each skill it finds is saved to a local SQLite database as
`(repo, name, description, commit)`, so later runs can query results across repositories.

- **Input:** a GitHub repository (URL or `owner/name`), or a GitHub organization or user URL
- **Output:** the list of skills in that repository, at a specific commit (for an organization:
  in each of its repositories, see *Scanning an organization*)

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
| `skill-atlas scan <owner URL>` | The same for every repository of a GitHub organization or user. See *Scanning an organization* |
| `skill-atlas list` | Print the skills saved in the DB |
| `skill-atlas serve` | Run the web UI: one input field, the same output as `scan`. See [web.md](web.md) |

### Options

| Option | Commands | Meaning |
|---|---|---|
| `--json` | scan, list | Print a JSON array of `{repo, name, description, commit, path, duplicates, content}` instead of text |
| `--color WHEN` | scan, list | `auto` (default), `always`, or `never`. See *Output format* |
| `--db PATH` | scan, list | SQLite DB path. Default: `$SKILL_ATLAS_DB`, or `~/.skill-atlas/atlas.db` if unset |
| `--ref REF` | scan | Branch or tag to scan (default: the remote's default branch). Not allowed with an owner URL |
| `--no-store` | scan | Print only; don't write to the DB |
| `--include-forks` | scan | With an owner URL: also scan the owner's forks (skipped by default) |
| `--jobs N` | scan | With an owner URL: clone up to `N` repositories at once. Default `4`, minimum `1` |
| `--repo URL` | list | Show only this repository's skills |

Accepted repository forms: `https://github.com/o/r`, `https://github.com/o/r.git`,
`github.com/o/r`, `git@github.com:o/r.git`, `o/r`. All of these normalize to
`https://github.com/o/r`. Any other git URL (e.g. `file://`) is passed to git as is.

### Scanning an organization

When the argument of `scan` is a GitHub **owner URL** rather than a repository, every repository
of that organization (or user) is scanned. Accepted owner forms: `https://github.com/<owner>`,
`github.com/<owner>`, `https://github.com/orgs/<owner>` (with or without `www.` and a trailing `/`).
All normalize to `https://github.com/<owner>`. `owner/name` and the other repository forms above
keep meaning a single repository; a bare `<owner>` is not an owner URL.

```
$ skill-atlas scan https://github.com/JetBrains
https://github.com/JetBrains: 3 repositories (1 fork skipped)

https://github.com/JetBrains/ideavim @ 7bd8f1315c8a

1. extensions-api-migration
   ...

6 skill(s) found

https://github.com/JetBrains/kotlin @ 848b4009281f
...

12 skill(s) found in 2 of 3 repositories
```

1. **Listing.** The repositories come from the GitHub REST API,
   `GET /users/<owner>/repos?type=owner&sort=full_name&per_page=100&page=N` (it serves organizations
   and users alike), page by page until a page has fewer than 100 entries. Only public repositories
   are listed. If `GITHUB_TOKEN` is set, it is sent as a bearer token, which raises the API rate
   limit (60 requests per hour without one); clones stay anonymous. The API base URL is
   `https://api.github.com`, or `$SKILL_ATLAS_GITHUB_API` if set (used by the tests).
2. **Filtering.** Forks are skipped unless `--include-forks` is given: a fork's skills belong to its
   upstream project. Archived repositories are scanned like any other.
3. **Scanning.** Each repository is scanned exactly like `skill-atlas scan https://github.com/<owner>/<name>`
   (same clone, rules and de-duplication), in name order (case-insensitive), up to `--jobs` at a time.
   Unless `--no-store` is given, each repository is saved to the DB as soon as its scan finishes, with the
   same replace semantics as a single scan, so an interrupted run keeps what it has already scanned.
   Repositories with 0 skills are stored too, so they appear in the web catalogue.
   Interrupting the run (Ctrl-C) stops it: queued repositories are not cloned (clones already running
   finish first), and the repositories already stored stay in the DB.
4. **Empty repositories** (no commits) are skipped with `warning: <repo>: skipping: repository is empty`.
   They are not stored and don't count as failures.
5. **Failures.** A repository that fails to clone doesn't stop the run: `error: <repo>: <git stderr>` is
   printed on stderr, its DB rows are left unchanged, and the run continues. The exit code is `1` if any
   repository failed, `0` otherwise.

Output:
- Text: a header line `https://github.com/<owner>: N repositories` (`1 repository`), with
  `(K forks skipped)` (`1 fork`) appended when forks were left out. Then, for each repository with at least one skill, the same block that a
  single `scan` prints (header, numbered list, summary), separated by blank lines. Repositories with
  0 skills are not printed. Last, a summary line: `S skill(s) found in R of N repositories`, or
  `No skills found in N repositories`, with `(F failed)` appended when repositories failed.
- Warnings are printed on stderr with the repository first: `warning: <repo>: skipping <path>: <reason>`.
- `--json`: one flat JSON array of every skill found, in the same order and with the same fields as
  `scan --json` (each item has its `repo`).

## What counts as a skill

A skill is a `SKILL.md` file that belongs to the **project's own agent workflow**:
the skills its developers use in `.agents/` or `.claude/`. Skills a project ships
to its users, keeps as test data, or pulls in from dependencies are not counted.
Three filters are applied in this order:

### a. Location: the project's own workflow

Only files at one of these paths count:

```
<prefix>/.agents/skills/<skill-dir>/SKILL.md
<prefix>/.claude/skills/<skill-dir>/SKILL.md
```

- `<prefix>` is either empty (the repo root) or any directory path, e.g. a subproject in a monorepo (`backend/.claude/skills/...`).
- `<skill-dir>` is exactly **one** directory level. `.claude/skills/SKILL.md` and `.claude/skills/a/b/SKILL.md` don't count.
- The file name `SKILL.md` is matched case-insensitively (`skill.md` and `Skill.md` also count).

Any other `SKILL.md` is ignored, e.g. `skills/pdf/SKILL.md`, `plugins/x/skills/pdf/SKILL.md`
or `docs/SKILL.md`. Those are the project's product or content, not its own workflow.

### b. Exclusions: shipped resources, tests, dependencies

A file that passes (a) is still ignored if any segment of its `<prefix>` is one of the
following (compared case-insensitively):

| Category | Segments |
|---|---|
| Skills shipped to users (e.g. inside a plugin) | `resources` |
| The project's own tests | `test`, `tests`, `testdata`, `test-data`, `fixtures`, `__tests__`, and any segment starting with `test` directly under `src` (e.g. `src/testFixtures`, `src/testIntegration`) |
| Vendored code and build output | `node_modules`, `vendor`, `build`, `out`, `dist` |

Only `<prefix>` is checked. `<skill-dir>` is not, so a skill named `test` in
`.claude/skills/test/SKILL.md` still counts.

### c. De-duplication: `.agents` vs `.claude`

Projects often keep the same skill in both `.agents/skills/` (read by several agents) and
`.claude/skills/` (read by Claude Code). Within the **same** `<prefix>`:

- If `.agents/skills` and `.claude/skills` contain skills with the same `name` (after frontmatter parsing),
  only **one** entry is reported, and its `path` is the `.agents` one. The paths of the merged
  `.claude` copies are kept in its `duplicates` list (in path order) and shown in the output, so every
  copy's location is visible.
- If the two files' contents differ, a warning is printed and the `.agents` copy is still used:
  `warning: <name>: .agents and .claude copies differ; using <prefix>/.agents/skills/<skill-dir>/SKILL.md`.
- Skills with the same name under **different** prefixes (`backend/.agents/skills/pdf` and `.agents/skills/pdf`)
  are separate skills, and both are reported.

### Other rules

- **Symlinks:** a `SKILL.md` that is a symlink is skipped with `warning: skipping <path>: symlink`.
  A symlinked **directory**, such as the common `.claude/skills -> ../.agents/skills`, is never
  checked out or followed, so it can't create a duplicate.
- **Ignored files are silent.** Files ruled out by (a) or (b) produce no output. Warnings are only
  for malformed files, symlinks, and conflicting duplicates.
- **Frontmatter:** the file must start with YAML frontmatter:

  ```markdown
  ---
  name: pdf
  description: Work with PDF files
  ---
  ...instructions...
  ```

  - `name` — taken from the frontmatter. If it's missing, `<skill-dir>` is used.
  - `description` — taken from the frontmatter, with whitespace collapsed to single spaces (so multi-line YAML becomes one line). Empty if missing.
  - `content` — everything after the closing `---`, whitespace-trimmed. Stored and included
    in `--json` output, but not shown in the text output (which stays as documented in
    *Output format* below); used to find similar skills (see *Similar skills* in [web.md](web.md)).
  - Files with no frontmatter or invalid frontmatter are skipped, with a `warning:` on stderr.

### Examples

| Path(s) in the repository | Result | Rule |
|---|---|---|
| `.claude/skills/pdf/SKILL.md` | ✅ 1 skill | a |
| `.agents/skills/pdf/SKILL.md` | ✅ 1 skill | a |
| `.agents/skills/pdf/SKILL.md` + `.claude/skills/pdf/SKILL.md` | ✅ 1 skill, path `.agents/skills/pdf/SKILL.md`, duplicates `[.claude/skills/pdf/SKILL.md]` | c |
| the same pair with different contents | ✅ 1 skill (`.agents` path) + warning | c |
| `backend/.claude/skills/deploy/SKILL.md` | ✅ 1 skill | a (monorepo prefix) |
| `backend/.agents/skills/pdf/SKILL.md` + `.agents/skills/pdf/SKILL.md` | ✅ 2 skills | c (different prefixes) |
| `.claude/skills/test/SKILL.md` | ✅ 1 skill | b checks the prefix only |
| `skills/pdf/SKILL.md`, `plugins/x/skills/pdf/SKILL.md`, `docs/SKILL.md` | ❌ ignored | a (outside `.agents`/`.claude`) |
| `.claude/skills/SKILL.md`, `.claude/skills/a/b/SKILL.md` | ❌ ignored | a (not exactly one `<skill-dir>`) |
| `plugin/src/main/resources/.claude/skills/x/SKILL.md` | ❌ ignored | b (shipped to users) |
| `src/test/resources/.claude/skills/x/SKILL.md` | ❌ ignored | b (tests) |
| `compiler/testData/.agents/skills/x/SKILL.md` | ❌ ignored | b (tests) |
| `src/testFixtures/.claude/skills/x/SKILL.md` | ❌ ignored | b (tests) |
| `node_modules/pkg/.claude/skills/x/SKILL.md` | ❌ ignored | b (vendored) |
| `.claude/skills/x/SKILL.md` as a symlink | ❌ skipped + warning | symlinks |

One intended consequence: repositories that *publish* skills as their product, such as
`anthropics/skills` with its `skills/*/SKILL.md`, report **0** skills. Those skills are
content, not the project's own workflow.

## Output format

Text output is a numbered list. Each entry takes several lines, with one field per line:

- Line 1: the number, right-aligned to the widest number, then the skill **name**.
- One indented `label: value` line per field, with values aligned in a column:
  - `scan`: `description`, `path`. The repo and commit appear once, in the header line.
  - `list`: `description`, `path`, `repo`, `commit`. Entries can come from several repositories, so each one shows its own.
- The `path` field lists **every copy** of the skill, one per line: first `path` (the copy that is used),
  then each of its `duplicates`, on continuation lines aligned with the value column:

  ```
  1. pdf
     description: Work with PDF files
     path:        .agents/skills/pdf/SKILL.md
                  .claude/skills/pdf/SKILL.md
  ```
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
cli.py ──► repo.py ──► discovery.py ──► parser.py ──► dedupe.py ──► store.py
 (argparse)  (normalize URL,  (rules a + b)   (YAML front-   (rule c)      (SQLite
   │          sparse clone,                     matter)                     persistence)
   │          commit SHA)
   └──► output.py (numbered multi-line rendering, colors)
                        models.Skill (repo, name, description, commit, path, content)
```

| Module | Responsibility |
|---|---|
| `cli.py` | Parses arguments, runs `scan`/`list` (`scan_owner()` for owner URLs), prints JSON, sets exit codes |
| `output.py` | `use_color()`, `Painter` (ANSI styling), `render_skills()` / `render_header()` / `render_summary()`, and the `warn()` / `error()` stderr helpers |
| `repo.py` | `normalize_repo_url()`, `github_owner_url()` (an owner URL's normalized form, or `None` for anything else) and `list_owner_repos()` (the owner's repositories from the GitHub API; see *Scanning an organization*). `clone()` is a context manager that clones into a temp dir, yields `(path, commit_sha)`, and deletes the temp dir afterwards |
| `discovery.py` | `find_skill_files(root)`: sorted list of `SKILL.md` paths that pass the location (a) and exclusion (b) rules. Symlinks are reported separately |
| `dedupe.py` | `dedupe(skills)`: applies rule c (merges `.agents`/`.claude` copies within a prefix, records the merged paths in `duplicates`, and warns when contents differ) |
| `parser.py` | `parse_frontmatter()` and `parse_skill()` → `(name, description, content)`. Raises `SkillParseError` on bad input |
| `models.py` | The `Skill` dataclass |
| `store.py` | The `Store` class: creates and migrates the schema, `replace_repo()`, `list()`, `repos()`, and the star methods used by the web UI |
| `similarity.py` | `find_similar()`: skills similar to a given one, by description and content. See *Similar skills* in [web.md](web.md) |

### Fetching strategy

The repository is cloned so that only skill files are downloaded:

1. `git clone --depth 1 --filter=blob:none --no-checkout [--branch REF] <url>` fetches one commit and its trees, but no file contents.
2. `git sparse-checkout set --no-cone` with two patterns limits the checkout to candidate locations (rule a):
   `**/.agents/skills/*/[Ss][Kk][Ii][Ll][Ll].[Mm][Dd]` and `**/.claude/skills/*/[Ss][Kk][Ii][Ll][Ll].[Mm][Dd]`.
3. `git checkout` downloads only those files.
4. `git rev-parse HEAD` gives the commit that was scanned.
5. Exclusions (rule b) are applied to the checked-out files in `discovery.py`. De-duplication (rule c)
   runs after parsing, because it needs each skill's `name`.

This keeps huge repositories cheap to scan: `JetBrains/kotlin` takes about 5 s instead of
downloading the full tree. Git LFS filters are disabled (`GIT_LFS_SKIP_SMUDGE=1`
plus `-c filter.lfs.*=` overrides), so git-lfs does not need to be installed.
`GIT_TERMINAL_PROMPT=0` makes clones of private or missing repositories fail
immediately instead of stopping to ask for a password.

## Data model

SQLite, three tables:

```sql
CREATE TABLE skills (
    repo        TEXT NOT NULL,   -- normalized URL
    path        TEXT NOT NULL,   -- SKILL.md path relative to the repo root
    name        TEXT NOT NULL,
    description TEXT,
    commit_sha  TEXT NOT NULL,   -- full 40-char SHA that was scanned
    duplicates  TEXT NOT NULL DEFAULT '[]',  -- JSON array of merged .claude copy paths (rule c)
    content     TEXT NOT NULL DEFAULT '',    -- SKILL.md body, after the frontmatter
    scanned_at  TEXT NOT NULL,   -- ISO-8601 UTC
    PRIMARY KEY (repo, path)
);

CREATE TABLE repos (             -- one row per scanned repository, even with 0 skills
    repo        TEXT PRIMARY KEY,
    commit_sha  TEXT NOT NULL,
    scanned_at  TEXT NOT NULL
);

CREATE TABLE stars (             -- one row per visitor who starred a skill in the web UI
    repo        TEXT NOT NULL,
    path        TEXT NOT NULL,   -- the skill's (repo, path), like skills' key
    visitor     TEXT NOT NULL,   -- random id from the visitor's cookie
    starred_at  TEXT NOT NULL,   -- ISO-8601 UTC
    PRIMARY KEY (repo, path, visitor)
);
```

`stars` has no foreign key to `skills`: a scan replaces a repository's `skills` rows but never touches
its stars, so stars survive rescans (see *Stars* in [web.md](web.md)). The CLI doesn't read it.

`repos` is what the web catalogue lists (see [web.md](web.md)). A DB created before it existed gets it
filled from `skills` when it is opened (repositories whose scan found 0 skills can't be recovered).

A DB created before the `duplicates` or `content` column existed gets it added (`ALTER TABLE`) when it
is opened; old rows read back with no duplicates and/or empty content until the repository is rescanned.

The key is `(repo, path)` rather than `(repo, name)`, because two skills in one repository can share a name.
A scan replaces **all** rows for its repository and upserts its `repos` row in a single transaction. Rescanning
never creates duplicates, and skills that were deleted upstream disappear from the DB.

## Errors and exit codes

| Situation | Behavior |
|---|---|
| Success, including 0 skills found | exit 0; prints "No skills found" when there are none |
| git missing, clone fails, or the repo/ref doesn't exist | `error: <git stderr>` on stderr, exit 1, DB unchanged |
| The repository has no commits | `error: repository is empty`, exit 1, DB unchanged (with an owner URL: a warning, see *Scanning an organization*) |
| Malformed `SKILL.md` | `warning: skipping <path>: <reason>` on stderr; the scan continues |
| Owner URL: the owner doesn't exist | `error: GitHub user or organization not found: <owner>`, exit 1, DB unchanged |
| Owner URL: the API fails (rate limit, network, a response that isn't a list) | `error: GitHub API: <reason>` (rate limit: plus a hint to set `GITHUB_TOKEN`), exit 1, DB unchanged |
| Owner URL: some repositories fail to clone | `error: <repo>: <git stderr>` for each; the others are scanned and stored; exit 1 |
| Owner URL with `--ref` | `error: --ref can't be used with an organization URL`, exit 2, nothing is cloned |
| Bad CLI arguments | argparse usage message, exit 2 |

## Testing

`pytest` covers:
- the parser, discovery, and URL normalization (unit tests)
- output: color decisions, number alignment, description wrapping
- the store: replace semantics, filtering, the `repos` table (0-skill repos, ordering, backfill of an old DB), stars (see [web.md](web.md)), `duplicates` round trip, and adding the column to an old DB
- end-to-end `scan` and `list` against a local git fixture repo, cloned through a `file://` URL (no network),
  including an empty repository (`error: repository is empty`)
- owner URLs (`tests/test_org_scan.py`): a local HTTP server stands in for the GitHub API
  (`SKILL_ATLAS_GITHUB_API`) and git's `url.<base>.insteadOf` redirects the clones to local fixture repos.
  One test per case of *Scanning an organization* and per owner-URL row of *Errors and exit codes*:
  every accepted owner form; pagination; forks skipped and `--include-forks`; text output (header,
  0-skill repos omitted, summaries) and `--json`; warnings prefixed with the repo; storage of every repo,
  including 0-skill ones, and `--no-store`; an empty repository (skipped with a warning); a failing repository; an unknown owner; an API error;
  an unexpected API response; `GITHUB_TOKEN` sent as a bearer token; `--ref` rejected; an interrupted run doesn't clone the queued repositories; `--jobs 1` and the default give the same output

Edge-case tests (`tests/test_edge_cases.py`) build a fixture repo for each scenario and run the
full clone → sparse checkout → discovery → parse → dedupe pipeline, so the sparse patterns
and the discovery rules are tested together:
- one test per row of the *Examples* table in "What counts as a skill"
- `.agents`/`.claude` pairs: identical (1 skill, no warning), different (1 skill + warning), a skill present in only one of them;
  the kept skill's `duplicates` and the text output list the `.claude` path
- a monorepo with several prefixes, each with its own `.agents`/`.claude` pair
- every exclusion segment from rule b, including case variants (`Resources`, `TestData`) and the `src/test*` rule
- case variants of the file name (`skill.md`, `Skill.md`) and near-misses (`SKILL.md.bak`, `skills.md`)
- symlinked `SKILL.md` files and a symlinked `.claude/skills` directory

Fixture repository (`tests/fixtures/edge-repo/`, tested by `tests/test_fixture_repo.py`):
a checked-in tree that contains all the edge cases above at once. It is copied to a temp dir, committed, and
scanned through `file://`. `tests/fixtures/edge-repo.expected.json` lists:
- the skills, in the exact expected order
- the exact warnings
- which `.claude` copies were merged into which `.agents` skills (checked against each skill's `duplicates`)
- every ignored path, with the rule that excludes it

A guard test fails if a fixture file isn't classified in that JSON. Another checks that the byte-level
cases (CRLF, BOM, symlinks) survive: `tests/fixtures/.gitattributes` sets `-text`.

### Continuous integration

`.github/workflows/tests.yml` runs `pytest` on every push to `main`, on every pull request, and on demand:
- Ubuntu with Python 3.14
- macOS (case-insensitive filesystem) with Python 3.14

Before the tests run, it checks that the fixture's symlinks and CRLF bytes survived the checkout.

A `changes` job runs first. If every file changed by the push or pull request is Markdown (`*.md`)
outside `tests/` (docs, `spec/`, `memory/`), the `pytest` jobs are skipped; a skipped job counts as
passing, so the PR still gets a green check. Markdown under `tests/` is fixture data and runs the
tests. Manual runs, new branches and pushes whose base commit is unknown always run the tests.
Per `AGENTS.md`, a change is done only when CI is green for its commit.

On pull requests, a `demo-video` job (Ubuntu, once per run, skipped by the same rule) re-records
`docs/demo.mp4` and compares screenshots at its key moments with `tests/demo_frames/`; any
visible difference fails it. See [demo-video.md](demo-video.md).

## Future work

- A GitHub API backend (Trees API + raw content) for environments without git.
- Private repositories via `GITHUB_TOKEN` (for owner URLs it is only used for the repository list).
- Scanning an organization from the web UI (see [web.md](web.md)).
- Skipping a rescan when the remote HEAD is unchanged (`git ls-remote` against the stored `commit_sha`).
- Other skill formats (e.g. `AGENTS.md`, Cursor rules) and extra frontmatter fields (`license`, `allowed-tools`).
