# skill-atlas Web — Architecture

## Purpose

A small web app for `skill-atlas`. It has **one input field**, for the repository URL,
and shows **the same output as the CLI**: the header, the numbered skill list, the summary line,
and any `warning:` / `error:` lines. Skill discovery, parsing and de-duplication are the
same code as the CLI (see [cli.md](cli.md)), so the results are always identical.

It also has a **catalogue** of every repository already in the database, so earlier scans can be
browsed without cloning again.

## Usage

```
$ skill-atlas serve
skill-atlas web UI on http://127.0.0.1:8000/
```

Open the URL, type a repository (`https://github.com/JetBrains/kotlin`, `JetBrains/kotlin`, …) and press **Scan**.

### Options

| Option | Meaning |
|---|---|
| `--host HOST` | Address to bind. Default `127.0.0.1` |
| `--port PORT` | Port to bind. Default `8000`; `0` picks a free port |
| `--db PATH` | SQLite DB path, same default as the CLI (`$SKILL_ATLAS_DB` or `~/.skill-atlas/atlas.db`) |
| `--no-store` | Don't write scan results to the DB |
| `--allow-local` | Also accept non-`https://` URLs, such as `file://`. Off by default; see *Security* |

The server uses only the Python standard library (`http.server`, threaded); no new dependencies.

## HTTP interface

| Request | Response |
|---|---|
| `GET /` | Home: the input field and the catalogue. `200` |
| `GET /?repo=` (empty or whitespace) | Same as `GET /`. `200` |
| `GET /?repo=<repo>` | Scans `<repo>` and returns the page with the input filled in and the output below it. `200` |
| `GET /?repo=<repo>` where the URL is not allowed | Page with `error: only https:// repository URLs are accepted`. `400`, nothing is cloned |
| `GET /?repo=<repo>` where the clone fails | Page with `error: <git stderr>`. `502`, DB unchanged |
| `GET /stored?repo=<repo>` | The stored skills of `<repo>`, read from the DB (no clone). `200` |
| `GET /stored?repo=<repo>` for a repo not in the DB, or with no `repo` | Page saying it isn't in the catalogue, with a *Scan it* link. `404` |
| `GET /similar?repo=<repo>&path=<path>` | Skills similar to the one at `<path>` in `<repo>`'s stored skills. `200` |
| `GET /similar?repo=<repo>&path=<path>` when that repo/path isn't stored, or `repo`/`path` is missing | Page saying it isn't in the catalogue, with a *Scan it* link. `404` |
| Any other path | `404` page with the scan form and a link home |

The form uses `GET`, so a result page has a shareable URL (`/?repo=JetBrains/kotlin`).

`<repo>` accepts the same forms as the CLI and is normalized the same way
(`owner/name` → `https://github.com/owner/name`). Results are saved to the DB just like
`skill-atlas scan`, unless the server runs with `--no-store`.

## Pages

Every page shares one layout: a top bar with the **skill-atlas** wordmark (links home) and a
*Catalogue* link with the number of stored repositories (`/#catalogue`), then the page content.
The `<title>` is `skill-atlas` on the home page and `<owner>/<name> · skill-atlas` on repository pages.

### Home (`/`)

1. A short headline and one sentence on what counts as a skill (`.agents/skills` and `.claude/skills`).
2. The scan form: the one input field and a **Scan** button.
3. The **catalogue** (`id="catalogue"`): every repository in the DB, most recently scanned first.
   Each entry is a link to `/stored?repo=<repo>` and shows:
   - the repository as `owner/name` for GitHub URLs (the full URL otherwise)
   - the number of skills (`0 skills`, `1 skill`, `N skills`)
   - the short commit (12 characters)
   - when it was scanned, in UTC (`YYYY-MM-DD HH:MM UTC`, with the ISO time in `<time datetime>`)

   Above the list: the totals (`N repositories · M skills`). There is no filter field: the page keeps
   exactly **one** input, the repository URL.
   With an empty DB, the catalogue says *No repositories yet* and invites a first scan.
   When the server runs with `--no-store`, a note says new scans aren't added.

   Repositories whose scan found **0 skills** are listed too (see the `repos` table in [cli.md](cli.md)).

### Scan result (`/?repo=<repo>`)

The form, with the input filled in, then the output panel (see *Output*). The panel's title bar
shows the equivalent command, `$ skill-atlas scan <repo>`, and a **Copy** button that copies the
output text. When the scan found at least one skill, the panel also has a **filter field** (see
*Skill filter*).

### Stored repository (`/stored?repo=<repo>`)

The scan form (empty), then the repository name, a summary line (skill count, commit, scan time,
and a *View on GitHub* link for GitHub repositories), a **Rescan** link to
`/?repo=<repo>`, and an output panel whose text is exactly what
`skill-atlas list --repo <repo> --color never` prints. The title bar shows that command. As on the
scan result page, the panel has a filter field when the repository has at least one stored skill.

Each skill's **name**, in the output panel, links to
`/similar?repo=<repo>&path=<path of that skill>` — see *Similar skills* below. Unlike the path's
GitHub link, this is an in-app link, so it opens in the same tab. There is no separate list: the
link is part of the same output panel, whose text keeps matching the CLI exactly (see *Output*).

### Similar skills (`/similar?repo=<repo>&path=<path>`)

The scan form (empty), then a breadcrumb back to the skill's repository
(`/stored?repo=<repo>`), the skill's name and path, and a list of similar skills — see
*Similar skills* below. Each entry links to `/stored?repo=<that skill's repo>`. With no
result above the threshold, the page says so instead of showing an empty list.
The title is `Similar to <skill name> · skill-atlas`.

If `repo`/`path` don't identify a stored skill (unknown repository, a path not in that
repository's stored skills, or either parameter missing), the response is the same 404 page
used by `/stored` for an unknown repository, offering to scan `repo` when one was given.

## Design

- Light and dark themes follow the system (`prefers-color-scheme`). Colors are CSS custom properties.
- The output panel always uses the dark terminal palette, in both themes, so the CLI colors read the same.
- System UI font for text; monospace for the output, commits, and paths.
- Layout works from 360 px wide up; the output panel scrolls horizontally instead of wrapping.
- Keyboard: the input is focused on the home page; `/` focuses it from anywhere on the page.
- Every page has exactly one `<input>` for the repository URL. An output panel that lists at
  least one skill also has a second, JS-only input: the skill filter (see *Skill filter*).
- JavaScript is only an enhancement (Copy button, `/` shortcut, *Scanning…* state, skill filter);
  every page works without it — the filter input is `hidden` until JS unhides it.
- No external requests: fonts, CSS, JS and the icon are inline.

## Output

The output block is a `<pre>` whose text is **exactly** what `skill-atlas scan --color never`
prints to stdout, with any stderr lines (`warning: …`) before it, in the order they were emitted:

```
warning: skipping .claude/skills/broken/SKILL.md: missing YAML frontmatter
https://github.com/o/r @ c823f9e564fd

1. review
   description: Review code carefully
   path:        .agents/skills/review/SKILL.md

1 skill(s) found
```

- Descriptions are wrapped at a fixed width of 100 columns (the CLI's default when there is no terminal).
- Colors are the CLI's colors, rendered as `<span class="…">` elements whose classes are the
  style names from `output.py` (`bold`, `dim`, `yellow`, `cyan`, `green`, `blue`, `magenta`, `red`).
  The page's CSS maps them to the palette of a dark terminal.
- Duplicated skills show all their paths, as in the CLI (see *Output format* in [cli.md](cli.md)).
- Each skill's **path is a link to the file on GitHub**, pinned to the scanned commit:
  `https://github.com/<owner>/<name>/blob/<full commit SHA>/<path>`, with the path percent-encoded
  per segment (`/` kept). Links open in a new tab (`target="_blank" rel="noopener"`).
  Only repositories that normalize to `https://github.com/<owner>/<name>` get links; for any other
  URL (e.g. `file://` with `--allow-local`) the path stays plain text. The link text is the path
  itself, so the `<pre>` text is unchanged. Every path is linked, including the paths of duplicates.
- On the stored-repository page only, each skill's **name is a link to its Similar skills page**
  (see below), the same way: the link text is just the name, so the `<pre>` text is unchanged.
  Unlike the path's GitHub link, it's an in-app link and doesn't open in a new tab.
- All text taken from the repository (names, descriptions, paths), from the DB, and from the input is HTML-escaped.

### Skill filter

When an output panel lists at least one skill (the scan result and stored-repository pages),
its title bar gains a text input, hidden until JavaScript runs, that narrows the list to skills
whose **name or description** contains the typed text (case-insensitive substring match; an empty
field shows everything). It filters only the numbered skill entries — the header line, the
"N skill(s) found/stored" summary, and any `warning:`/`error:` lines are always shown.

Each skill's rendered block is wrapped in a `<span class="skill" data-name="…" data-desc="…">`
carrying its unescaped-for-matching name and description as HTML attributes; the wrapper adds no
visible text, so the `<pre>` content is unaffected. Filtering toggles a `skill--hidden` class
(`display: none`) on non-matching spans. When nothing matches, a "No matching skills." note below
the `<pre>` is shown. There is no server round-trip: the full list is always rendered, and the
filter only hides/shows elements already on the page.

While a scan is running, the button shows *Scanning…* and is disabled.

## Similar skills

Every stored skill can be compared against every other skill stored in the database, across all
repositories, to find similar ones — reuse and overlap are often invisible until you can see that
two repositories independently wrote near-identical skills.

- **Similarity** of two skills is the average of the `SequenceMatcher.ratio()` (Python's
  `difflib`, stdlib) of their `description`s and of their `content`s (the `SKILL.md` body,
  after the frontmatter — see *Frontmatter* in [cli.md](cli.md)), each in `[0, 1]`. Averaging
  keeps the (often much longer) content from drowning out the description in the score.
- Only skills with similarity **strictly greater than 10%** are shown.
- Results are sorted by **descending similarity**; ties break by repository, then skill name.
- A skill is never compared against itself. Two rows with the same `(repo, path)` never both
  appear; distinct paths (e.g. `.agents`/`.claude` duplicates, which are already merged into one
  stored row — see rule (c) in [cli.md](cli.md)) are ordinary candidates like any other.
- The comparison only ever looks at what's already **stored** in the database — it never
  reaches out to a repository, so it works offline and doesn't depend on the scanning
  repository still being reachable.
- Each result shows the similar skill's **name** and its **similarity**, as a percentage with
  one decimal place (e.g. `23.5%`), plus its repository so a same-named skill from two different
  repositories can be told apart.

`skill_atlas.similarity.find_similar(target, candidates, threshold=0.10)` implements this; see
its docstring and `similarity.py`'s row in [cli.md](cli.md)'s *Components* table.

## Security

The server clones whatever URL a visitor types, so by default only URLs that normalize to
`https://…` are accepted. This rules out `file://` (reading the server's own disk), `ssh`/`git@`
URLs other than GitHub's, which normalize to `https://` (using the server's SSH keys), `ext::` transports, and arguments starting with `-` that git
would read as options. `--allow-local` lifts the restriction and is meant for local use and tests.
The default bind address is `127.0.0.1`.

## Components

```
web.py ──► cli.scan_repo() ──► (same pipeline as the CLI)
   │
   └──► output.render_header / render_skills / render_summary with HtmlPainter
```

| Module | Responsibility |
|---|---|
| `web.py` | `HtmlPainter` (a `Painter` that escapes HTML, emits `<span>`s, and renders `link()` as `<a>`), `_skill_wrap()` (the `data-name`/`data-desc` wrapper for the skill filter), the page renderers (`render_home()`, `render_scan()`, `render_stored()`, `render_similar()`, `render_not_found()`), the request handler, and `make_server()` |
| `store.py` | `Store.repos()`: one `RepoEntry(repo, commit, scanned_at, skills)` per repository, most recent first |
| `output.py` | `Painter.link(text, url, *styles)`: plain styled text in the terminal; `render_skills()` passes each path's GitHub URL through it |
| `output.py` | `render_skills()` / `render_list()` take optional `name_url(skill)` (link the name, for *Similar skills*) and `wrap(skill, block)` (wrap each skill's block, for the filter) callbacks, used only by the web UI, without changing the CLI's plain-text output |
| `repo.py` | `github_blob_url(repo, commit, path)`: the file's GitHub URL, or `None` for non-GitHub repos |
| `similarity.py` | `find_similar(target, candidates, threshold)`: see *Similar skills* above |
| `cli.py` | The `serve` subcommand. `scan_repo()` takes a `warn` callback so the web page can collect warnings instead of printing them |

## Testing

`tests/test_web.py` starts the server on port `0` in a background thread and makes real HTTP
requests against a local git fixture repo (`file://`, with `allow_local=True`). One test per
row of the *HTTP interface* table, plus:
- the `<pre>` text (tags stripped, entities unescaped) equals `skill-atlas scan --color never` stdout for the same repo
- warnings appear in the output
- a skill whose name/description contains `<script>` is escaped, and so is the echoed input
- paths link to `https://github.com/o/r/blob/<sha>/<path>` for a GitHub URL (the clone is
  redirected to the local fixture with git's `url.<base>.insteadOf`, so no network is used),
  non-ASCII paths are percent-encoded, a duplicated skill shows and links both of its paths,
  and `file://` repos get no links
- color spans are present (`<span class="bold cyan">`)
- without `allow_local`, `file://`, non-GitHub `git@` and `-`-prefixed input get `400` and nothing is stored
- results are stored in the DB, and not stored with `store=False`
- catalogue: lists every scanned repository with its skill count, short commit and scan time,
  most recent first; includes a 0-skill repository; links to `/stored`; shows the empty state and the
  `--no-store` note; escapes stored text; the top bar shows the repository count
- `/stored?repo=`: accepts the same input forms as scan; its `<pre>` text equals
  `skill-atlas list --repo <repo> --color never`; `404` for unknown or missing `repo`; links to rescan
- `/stored?repo=`: each skill's name, inside the `<pre>`, links to `/similar?repo=&path=` (in the same
  tab, unlike the path's GitHub link), and the `<pre>` text is unaffected once tags are stripped
- `/similar?repo=&path=`: results above 10% shown with name and one-decimal percentage, sorted descending;
  the target skill itself and skills at or below 10% are excluded; `404` for an unknown repo, an unknown path,
  or a missing parameter; links back to the skill's own repository and to each result's repository
- the page `<title>` for home and repository pages; the repository `<input>` is on every page, and
  the filter `<input>` is present (`data-filter`, `hidden`) only when the output lists a skill and
  absent for 0-skill scans/repositories; skill names/descriptions in `data-name`/`data-desc` are escaped
