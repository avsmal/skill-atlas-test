# skill-atlas Web — Architecture

## Purpose

A small web page for `skill-atlas scan`. It has **one input field**, for the repository URL,
and shows **the same output as the CLI**: the header, the numbered skill list, the summary line,
and any `warning:` / `error:` lines. Skill discovery, parsing and de-duplication are the
same code as the CLI (see [cli.md](cli.md)), so the results are always identical.

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
| `GET /` | The page with an empty input field and no output. `200` |
| `GET /?repo=` (empty or whitespace) | Same as `GET /`. `200` |
| `GET /?repo=<repo>` | Scans `<repo>` and returns the page with the input filled in and the output below it. `200` |
| `GET /?repo=<repo>` where the URL is not allowed | Page with `error: only https:// repository URLs are accepted`. `400`, nothing is cloned |
| `GET /?repo=<repo>` where the clone fails | Page with `error: <git stderr>`. `502`, DB unchanged |
| Any other path | `404` |

The form uses `GET`, so a result page has a shareable URL (`/?repo=JetBrains/kotlin`).

`<repo>` accepts the same forms as the CLI and is normalized the same way
(`owner/name` → `https://github.com/owner/name`). Results are saved to the DB just like
`skill-atlas scan`, unless the server runs with `--no-store`.

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
- All text taken from the repository (names, descriptions, paths) and from the input is HTML-escaped.

While a scan is running, the button shows *Scanning…* and is disabled.

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
| `web.py` | `HtmlPainter` (a `Painter` that escapes HTML, emits `<span>`s, and renders `link()` as `<a>`), `render_page()`, the request handler, and `make_server()` |
| `output.py` | `Painter.link(text, url, *styles)`: plain styled text in the terminal; `render_skills()` passes each path's GitHub URL through it |
| `repo.py` | `github_blob_url(repo, commit, path)`: the file's GitHub URL, or `None` for non-GitHub repos |
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
