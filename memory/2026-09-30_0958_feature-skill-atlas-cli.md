# PR #3 — Web UI (`skill-atlas serve`) and all paths of duplicated skills

- **Date/time:** 2026-09-30, discussion started 09:39 UTC, PR opened 09:58 UTC, merged 10:01 UTC
- **Branch:** `feature/skill-atlas-cli`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/3

## What was asked
- A web interface, specified first (asked as `specs/web.md`; written to `spec/web.md`, the real folder).
- Exactly one input field (the repo URL); output identical to the CLI.
- Skill file paths link to the file on GitHub.
- For duplicated skills, show every path.

## What was decided / built
- Stdlib-only `http.server`; reuses `scan_repo()` and the `output.py` renderers; `HtmlPainter`
  maps ANSI styles to `<span class>`. Test asserts page text == `scan --color never` stdout.
- `GET /?repo=…` gives shareable URLs; results are stored like `scan`. Options `--host`, `--port`,
  `--db`, `--no-store`, `--allow-local`.
- Links go to `/blob/<sha>/<path>` at the scanned commit; non-GitHub repos get plain text.
- Security: by default only URLs normalizing to `https://` are cloned and the server binds to
  `127.0.0.1`; input starting with `-` is rejected. `--allow-local` relaxes this.
- `Skill.duplicates` keeps merged `.claude` paths; `--json` items always have `duplicates`;
  new DB column added via `ALTER TABLE` on open.
