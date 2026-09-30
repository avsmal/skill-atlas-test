"""Web UI for skill-atlas: one input field, the same output as ``skill-atlas scan``.

See spec/web.md.
"""
from __future__ import annotations

import html
import re
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .output import Painter, render_header, render_skills, render_summary
from .repo import RepoError, normalize_repo_url
from .store import Store

WIDTH = 100
NOT_ALLOWED = "only https:// repository URLs are accepted"


class HtmlPainter(Painter):
    """Escapes text and renders styles as ``<span class="…">`` instead of ANSI codes."""

    def __init__(self) -> None:
        super().__init__(True)

    def __call__(self, text: str, *styles: str) -> str:
        text = html.escape(text, quote=False)
        if not styles:
            return text
        return f'<span class="{" ".join(styles)}">{text}</span>'

    def link(self, text: str, url: str | None, *styles: str) -> str:
        inner = self(text, *styles)
        if not url:
            return inner
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{inner}</a>'


def run_scan(repo_input: str, db: Path, *, store: bool, allow_local: bool) -> tuple[HTTPStatus, str]:
    """Scan ``repo_input``; return the status and the HTML for the ``<pre>`` block."""
    from .cli import scan_repo  # imported lazily: cli imports this module for `serve`

    paint = HtmlPainter()
    lines: list[str] = []

    def warn(msg: str) -> None:
        lines.append(f"{paint('warning:', 'bold', 'yellow')} {paint(msg)}")

    def error(msg: str) -> str:
        lines.append(f"{paint('error:', 'bold', 'red')} {paint(msg)}")
        return "\n".join(lines)

    if not allow_local and not normalize_repo_url(repo_input).startswith("https://"):
        return HTTPStatus.BAD_REQUEST, error(NOT_ALLOWED)
    try:
        repo, commit, skills = scan_repo(repo_input, warn=warn)
    except RepoError as e:
        return HTTPStatus.BAD_GATEWAY, error(str(e))
    if store:
        with Store(db) as s:
            s.replace_repo(repo, skills)

    lines += [render_header(repo, commit, paint), ""]
    if skills:
        lines += [render_skills(skills, paint, width=WIDTH), ""]
    lines.append(render_summary(len(skills), paint))
    return HTTPStatus.OK, "\n".join(lines)


def render_page(repo_input: str = "", output: str | None = None) -> str:
    subs = {
        "value": html.escape(repo_input),
        "output": f'<pre class="output">{output}</pre>' if output is not None else "",
    }
    # one pass, so placeholders inside the substituted text are left alone
    return re.sub(r"\{\{(value|output)\}\}", lambda m: subs[m[1]], _PAGE)


class Handler(BaseHTTPRequestHandler):
    server_version = "skill-atlas"

    def __init__(self, *args, db: Path, store: bool, allow_local: bool, **kwargs):
        self.db, self.store, self.allow_local = db, store, allow_local
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path != "/":
            self._send(HTTPStatus.NOT_FOUND, render_page(output=html.escape(f"not found: {url.path}")))
            return
        repo_input = (parse_qs(url.query).get("repo") or [""])[0].strip()
        if not repo_input:
            self._send(HTTPStatus.OK, render_page())
            return
        status, output = run_scan(repo_input, self.db, store=self.store, allow_local=self.allow_local)
        self._send(status, render_page(repo_input, output))

    def _send(self, status: HTTPStatus, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(
    host: str, port: int, db: Path | str, *, store: bool = True, allow_local: bool = False,
) -> ThreadingHTTPServer:
    handler = partial(Handler, db=Path(db), store=store, allow_local=allow_local)
    return ThreadingHTTPServer((host, port), handler)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>skill-atlas</title>
<style>
  :root { color-scheme: light dark; --bg: #f6f7f9; --fg: #1d2330; --term-bg: #16181d; --term-fg: #d7dae0;
          --accent: #2f6fde; --border: #d4d8e0; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #0f1115; --fg: #e3e6eb; --border: #2b303a; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 32px 16px; background: var(--bg); color: var(--fg);
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width: 960px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 16px; }
  form { display: flex; gap: 8px; }
  input { flex: 1; min-width: 0; padding: 10px 12px; font: inherit; border: 1px solid var(--border);
          border-radius: 6px; background: transparent; color: inherit; }
  button { padding: 10px 18px; font: inherit; font-weight: 600; border: 0; border-radius: 6px;
           background: var(--accent); color: #fff; cursor: pointer; }
  button:disabled { opacity: .6; cursor: progress; }
  .output { margin: 20px 0 0; padding: 16px; overflow-x: auto; border-radius: 8px;
            background: var(--term-bg); color: var(--term-fg);
            font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .output a { color: inherit; text-decoration: underline; text-decoration-color: rgba(158,206,106,.4);
              text-underline-offset: 2px; }
  .output a:hover { text-decoration-color: currentColor; }
  .bold { font-weight: 700; } .dim { opacity: .6; }
  .red { color: #f7768e; } .green { color: #9ece6a; } .yellow { color: #e0af68; }
  .blue { color: #7aa2f7; } .magenta { color: #bb9af7; } .cyan { color: #7dcfff; }
</style>
</head>
<body>
<main>
  <h1>skill-atlas</h1>
  <form method="get" action="/">
    <input name="repo" value="{{value}}" placeholder="https://github.com/owner/name" aria-label="Repository URL" autofocus required>
    <button type="submit">Scan</button>
  </form>
  {{output}}
</main>
<script>
  document.querySelector("form").addEventListener("submit", e => {
    const b = e.target.querySelector("button"); b.disabled = true; b.textContent = "Scanning\\u2026";
  });
  window.addEventListener("pageshow", () => {
    const b = document.querySelector("button"); b.disabled = false; b.textContent = "Scan";
  });
</script>
</body>
</html>
"""
