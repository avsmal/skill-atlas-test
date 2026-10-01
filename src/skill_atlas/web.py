"""Web UI for skill-atlas: one input field, the same output as the CLI, and a catalogue.

See spec/web.md.
"""
from __future__ import annotations

import html
import json
import re
import secrets
import shlex
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from .models import RepoEntry, Skill
from .output import Painter, render_header, render_list, render_skills, render_summary
from .repo import RepoError, github_slug, normalize_repo_url
from .similarity import DEFAULT_THRESHOLD, find_similar
from .store import Store

WIDTH = 100
NOT_ALLOWED = "only https:// repository URLs are accepted"
VISITOR_COOKIE = "skill_atlas_visitor"
_VISITOR_RE = re.compile(r"[A-Za-z0-9_-]{22}")  # secrets.token_urlsafe(16)
_VISITOR_MAX_AGE = 5 * 365 * 24 * 3600


class HtmlPainter(Painter):
    """Escapes text and renders styles as ``<span class="…">`` instead of ANSI codes."""

    def __init__(self) -> None:
        super().__init__(True)

    def __call__(self, text: str, *styles: str) -> str:
        text = html.escape(text, quote=False)
        if not styles:
            return text
        return f'<span class="{" ".join(styles)}">{text}</span>'

    def link(self, text: str, url: str | None, *styles: str, external: bool = True) -> str:
        inner = self(text, *styles)
        if not url:
            return inner
        target = ' target="_blank" rel="noopener"' if external else ""
        return f'<a href="{html.escape(url)}"{target}>{inner}</a>'


# --- Output (the <pre> text, identical to the CLI) -------------------------------------

def run_scan(
    repo_input: str, db: Path, *, store: bool, allow_local: bool, visitor: str | None = None,
) -> tuple[HTTPStatus, str, int]:
    """Scan ``repo_input``; return the status, the HTML for the ``<pre>`` block, and the skill count.

    When the result is saved, each skill gets a star button (``visitor``'s stars are shown pressed).
    """
    from .cli import scan_repo  # imported lazily: cli imports this module for `serve`

    paint = HtmlPainter()
    lines: list[str] = []

    def warn(msg: str) -> None:
        lines.append(f"{paint('warning:', 'bold', 'yellow')} {paint(msg)}")

    def error(msg: str) -> tuple[str, int]:
        lines.append(f"{paint('error:', 'bold', 'red')} {paint(msg)}")
        return "\n".join(lines), 0

    if not allow_local and not normalize_repo_url(repo_input).startswith("https://"):
        text, count = error(NOT_ALLOWED)
        return HTTPStatus.BAD_REQUEST, text, count
    try:
        repo, commit, skills = scan_repo(repo_input, warn=warn)
    except RepoError as exc:
        text, count = error(str(exc))
        return HTTPStatus.BAD_GATEWAY, text, count
    stars = None
    if store:
        with Store(db) as s:
            s.replace_repo(repo, skills, commit)
            stars = Stars.load(s, repo, visitor, stored_url(repo))

    lines += [render_header(repo, commit, paint), ""]
    if skills:
        suffix = stars.button if stars else None
        lines += [render_skills(skills, paint, width=WIDTH, name_suffix=suffix, wrap=_skill_wrap), ""]
    lines.append(render_summary(len(skills), paint))
    return HTTPStatus.OK, "\n".join(lines), len(skills)


# --- Pages ------------------------------------------------------------------------------

def e(text: object) -> str:
    return html.escape(str(text))


def display_repo(repo: str) -> str:
    return github_slug(repo) or repo


def _skill_wrap(skill: Skill, block: str) -> str:
    """Wraps a rendered skill block for the client-side name/description filter."""
    return f'<span class="skill" data-name="{e(skill.name)}" data-desc="{e(skill.description)}">{block}</span>'


def stored_url(repo: str) -> str:
    return "/stored?repo=" + quote(repo, safe="")


def scan_url(repo: str) -> str:
    return "/?repo=" + quote(repo, safe="")


def similar_url(repo: str, path: str) -> str:
    return f"/similar?repo={quote(repo, safe='')}&path={quote(path, safe='')}"


def star_url(repo: str, path: str, *, star: bool, next_url: str) -> str:
    return (
        f"/star?repo={quote(repo, safe='')}&path={quote(path, safe='')}"
        f"&star={int(star)}&next={quote(next_url, safe='')}"
    )


def safe_next(next_url: str) -> str | None:
    """``next_url`` if it's a path on this server (no open redirect, no header injection)."""
    if not re.fullmatch(r"/(?!/)[!-~]*", next_url) or "\\" in next_url:
        return None
    return next_url


@dataclass(frozen=True)
class Stars:
    """Star counts and the current visitor's stars, for rendering star buttons."""

    counts: dict[tuple[str, str], int]
    mine: set[tuple[str, str]]
    next_url: str  # where the no-JS form submission returns to

    @classmethod
    def load(cls, store: Store, repo: str, visitor: str | None, next_url: str) -> "Stars":
        mine = store.starred_by(visitor) if visitor else set()
        return cls(store.star_counts(repo), mine, next_url)

    def button(self, skill: Skill, *, big: bool = False) -> str:
        """A star toggle with no text of its own (CSS draws ``☆ N``), so the ``<pre>`` text is unchanged."""
        key = (skill.repo, skill.path)
        count, starred = self.counts.get(key, 0), key in self.mine
        action = star_url(skill.repo, skill.path, star=not starred, next_url=self.next_url)
        cls = "star star--big" if big else "star"
        return (
            f'<button type="submit" class="{cls}" form="star-form" formaction="{e(action)}" data-star'
            f' data-stars="{count}" aria-pressed="{str(starred).lower()}"'
            f' aria-label="Star {e(skill.name)}" title="{plural(count, "star")}"></button>'
        )


def format_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


def _badge(skills: int) -> str:
    cls = "badge badge--zero" if skills == 0 else "badge"
    return f'<span class="{cls}">{plural(skills, "skill")}</span>'


def _form(value: str = "", *, hero: bool = False) -> str:
    cls = "scan scan--hero" if hero else "scan"
    return f"""<form class="{cls}" method="get" action="/" role="search">
  <label class="scan__field">
    <span class="visually-hidden">Repository URL</span>
    {_ICON_SEARCH}
    <input name="repo" value="{e(value)}" placeholder="https://github.com/owner/name  or  owner/name"
           autocomplete="off" autocapitalize="off" spellcheck="false" required{" autofocus" if hero else ""}>
    <kbd class="scan__kbd" aria-hidden="true">/</kbd>
  </label>
  <button type="submit">Scan</button>
</form>"""


def _terminal(command: str, output: str, *, failed: bool = False, filterable: bool = False) -> str:
    cls = "term term--failed" if failed else "term"
    filter_field = f"""
  <div class="term__filter">
    {_ICON_SEARCH}
    <input type="search" class="term__filter-input" data-filter hidden
           placeholder="Filter skills…" aria-label="Filter skills by name or description">
  </div>""" if filterable else ""
    empty_note = (
        '\n  <p class="term__empty" data-filter-empty hidden>No matching skills.</p>' if filterable else ""
    )
    return f"""<section class="{cls}" aria-label="Output">
  <div class="term__bar">
    <span class="term__dots" aria-hidden="true"><i></i><i></i><i></i></span>
    <code class="term__cmd"><span class="term__prompt">$</span> {e(command)}</code>
    <button type="button" class="term__copy" data-copy hidden>Copy</button>
  </div>{filter_field}
  <pre class="output">{output}</pre>{empty_note}
</section>"""


def _layout(title: str, body: str, *, repo_count: int) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{e(title)}</title>
<link rel="icon" href="data:image/svg+xml,{quote(_ICON_LOGO_FAVICON)}">
<style>{_CSS}</style>
</head>
<body>
<div class="progress" aria-hidden="true"></div>
<header class="topbar">
  <div class="wrap topbar__inner">
    <a class="brand" href="/">{_ICON_LOGO}<span>skill-atlas</span></a>
    <nav><a class="nav-link" href="/#catalogue">Catalogue <span class="count">{repo_count}</span></a></nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<form id="star-form" method="post" action="/star" hidden></form>
<footer class="wrap"><p class="footer">
  Lists the <code>SKILL.md</code> files under <code>.agents/skills</code> and <code>.claude/skills</code>
  that a project's own developers use. Same engine as the <code>skill-atlas</code> CLI.
</p></footer>
<script>{_JS}</script>
</body>
</html>
"""


def _catalogue(entries: list[RepoEntry], *, store: bool) -> str:
    note = "" if store else (
        '<p class="note">This server runs with <code>--no-store</code>: new scans are not added to the catalogue.</p>'
    )
    if not entries:
        return f"""<section class="catalogue" id="catalogue">
  <div class="section-head"><h2>Catalogue</h2></div>
  {note}
  <div class="empty">
    <p><strong>No repositories yet.</strong></p>
    <p>Scan one above and it will appear here.</p>
  </div>
</section>"""
    rows = []
    for r in entries:
        slug = github_slug(r.repo)
        if slug:
            owner, name = slug.split("/", 1)
            label = f'<span class="repo__owner">{e(owner)}/</span><span class="repo__name">{e(name)}</span>'
        else:
            label = f'<span class="repo__name">{e(r.repo)}</span>'
        rows.append(f"""<li><a class="repo" href="{e(stored_url(r.repo))}">
    <span class="repo__title">{label}</span>
    <span class="repo__meta">
      {_badge(r.skills)}
      <code class="repo__commit">{e(r.commit[:12])}</code>
      <time datetime="{e(r.scanned_at)}">{e(format_time(r.scanned_at))}</time>
    </span>
  </a></li>""")
    totals = f'{plural(len(entries), "repository", "repositories")} · {plural(sum(r.skills for r in entries), "skill")}'
    return f"""<section class="catalogue" id="catalogue">
  <div class="section-head">
    <h2>Catalogue</h2>
    <p class="muted">{totals}</p>
  </div>
  {note}
  <ul class="repo-list">
  {"".join(rows)}
  </ul>
</section>"""


def _top_starred(top: list[tuple[Skill, int]]) -> str:
    if not top:
        return ""
    rows = "".join(f"""<li><a class="repo" href="{e(similar_url(skill.repo, skill.path))}">
    <span class="repo__title"><span class="repo__name">{e(skill.name)}</span></span>
    <span class="repo__meta">
      <span class="badge badge--star">★ {count}</span>
      <span class="muted">{e(display_repo(skill.repo))}</span>
    </span>
  </a></li>""" for skill, count in top)
    return f"""
<section class="starred" id="starred">
  <div class="section-head"><h2>Most starred</h2></div>
  <ul class="repo-list">
  {rows}
  </ul>
</section>"""


def render_home(
    entries: list[RepoEntry], *, store: bool, top: list[tuple[Skill, int]] | None = None,
) -> str:
    body = f"""<section class="hero">
  <h1>Find the agent skills a repository uses</h1>
  <p class="lede">Paste a GitHub repository. skill-atlas checks out only its
  <code>.agents/skills</code> and <code>.claude/skills</code> folders and lists every skill at the current commit.</p>
  {_form(hero=True)}
</section>{_top_starred(top or [])}
{_catalogue(entries, store=store)}"""
    return _layout("skill-atlas", body, repo_count=len(entries))


def render_scan(
    repo_input: str, status: HTTPStatus, output: str, *, repo_count: int, skill_count: int,
) -> str:
    repo = normalize_repo_url(repo_input)
    title = f"{display_repo(repo)} · skill-atlas" if status == HTTPStatus.OK else "skill-atlas"
    body = f"""{_form(repo_input)}
{_terminal(
        f"skill-atlas scan {shlex.quote(repo_input)}", output,
        failed=status != HTTPStatus.OK, filterable=skill_count > 0,
    )}"""
    return _layout(title, body, repo_count=repo_count)


def render_stored(entry: RepoEntry, output: str, *, repo_count: int) -> str:
    shown = display_repo(entry.repo)
    github = (
        f'<a class="btn btn--ghost" href="{e(entry.repo)}" target="_blank" rel="noopener">View on GitHub</a>'
        if github_slug(entry.repo) else ""
    )
    body = f"""{_form()}
<section class="repo-head">
  <p class="crumbs"><a href="/#catalogue">Catalogue</a> <span aria-hidden="true">/</span></p>
  <h1>{e(shown)}</h1>
  <div class="repo-head__row">
    <p class="facts">
      {_badge(entry.skills)}
      <span>commit <code>{e(entry.commit[:12])}</code></span>
      <span>scanned <time datetime="{e(entry.scanned_at)}">{e(format_time(entry.scanned_at))}</time></span>
    </p>
    <div class="actions">
      {github}
      <a class="btn" href="{e(scan_url(entry.repo))}">Rescan</a>
    </div>
  </div>
</section>
{_terminal(f"skill-atlas list --repo {shlex.quote(entry.repo)}", output, filterable=entry.skills > 0)}"""
    return _layout(f"{shown} · skill-atlas", body, repo_count=repo_count)


def render_similar(
    skill: Skill, results: list[tuple[Skill, float]], *, star_button: str, repo_count: int,
) -> str:
    if results:
        rows = "".join(f"""<li><a class="repo" href="{e(stored_url(other.repo))}">
    <span class="repo__title"><span class="repo__name">{e(other.name)}</span></span>
    <span class="repo__meta">
      <span class="badge">{ratio * 100:.1f}%</span>
      <span class="muted">{e(display_repo(other.repo))}</span>
    </span>
  </a></li>""" for other, ratio in results)
        list_html = f'<ul class="repo-list">\n  {rows}\n  </ul>'
    else:
        list_html = f"""<div class="empty">
  <p><strong>No similar skills found.</strong></p>
  <p>No stored skill is more than {DEFAULT_THRESHOLD:.0%} similar.</p>
</div>"""
    body = f"""{_form()}
<section class="repo-head">
  <p class="crumbs"><a href="{e(stored_url(skill.repo))}">{e(display_repo(skill.repo))}</a> <span aria-hidden="true">/</span></p>
  <h1>Similar to {e(skill.name)}</h1>
  <div class="repo-head__row">
    <p class="facts"><code>{e(skill.path)}</code></p>
    <div class="actions">{star_button}</div>
  </div>
</section>
<section class="similar">
  <div class="section-head"><h2>Similar skills</h2></div>
  {list_html}
</section>"""
    return _layout(f"Similar to {skill.name} · skill-atlas", body, repo_count=repo_count)


def render_not_found(
    message: str, *, repo: str | None = None, repo_count: int, title: str = "Not found",
) -> str:
    action = (
        f'<a class="btn" href="{e(scan_url(repo))}">Scan it</a>' if repo
        else '<a class="btn" href="/">Go home</a>'
    )
    body = f"""{_form()}
<section class="empty empty--page">
  <p><strong>{e(message)}</strong></p>
  <p>{action}</p>
</section>"""
    return _layout(f"{title} · skill-atlas", body, repo_count=repo_count)


# --- HTTP -------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "skill-atlas"

    def __init__(self, *args, db: Path, store: bool, allow_local: bool, **kwargs):
        self.db, self.store, self.allow_local = db, store, allow_local
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        repo_input = (query.get("repo") or [""])[0].strip()
        if url.path == "/":
            self._index(repo_input)
        elif url.path == "/stored":
            self._stored(repo_input)
        elif url.path == "/similar":
            self._similar(repo_input, (query.get("path") or [""])[0])
        else:
            self._send(HTTPStatus.NOT_FOUND, render_not_found(
                f"Page not found: {url.path}", repo_count=len(self._repos()),
            ))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(min(length, 65536))  # the star form sends no fields; drain any body
        url = urlsplit(self.path)
        if url.path == "/star":
            self._star(parse_qs(url.query))
        else:
            self._send(HTTPStatus.NOT_FOUND, render_not_found(
                f"Page not found: {url.path}", repo_count=len(self._repos()),
            ))

    def _index(self, repo_input: str) -> None:
        if not repo_input:
            top: list[tuple[Skill, int]] = []
            if self.db.exists():
                with Store(self.db) as s:
                    top = s.top_starred()
            self._send(HTTPStatus.OK, render_home(self._repos(), store=self.store, top=top))
            return
        status, output, skill_count = run_scan(
            repo_input, self.db, store=self.store, allow_local=self.allow_local, visitor=self._visitor(),
        )
        self._send(status, render_scan(
            repo_input, status, output, repo_count=len(self._repos()), skill_count=skill_count,
        ))

    def _stored(self, repo_input: str) -> None:
        entries = self._repos()
        if not repo_input:
            self._send(HTTPStatus.NOT_FOUND, render_not_found("No repository given.", repo_count=len(entries)))
            return
        repo = normalize_repo_url(repo_input)
        entry = next((r for r in entries if r.repo == repo), None)
        if entry is None:
            self._send(HTTPStatus.NOT_FOUND, render_not_found(
                f"{display_repo(repo)} isn't in the catalogue yet.", repo=repo, repo_count=len(entries),
            ))
            return
        with Store(self.db) as s:
            skills = s.list(repo)
            stars = Stars.load(s, repo, self._visitor(), stored_url(repo))
        output = render_list(
            skills, HtmlPainter(), width=WIDTH,
            name_url=lambda sk: similar_url(sk.repo, sk.path), name_suffix=stars.button, wrap=_skill_wrap,
        )
        self._send(HTTPStatus.OK, render_stored(entry, output, repo_count=len(entries)))

    def _similar(self, repo_input: str, path: str) -> None:
        skill, entries = self._stored_skill(repo_input, path)
        if skill is None:
            return
        with Store(self.db) as s:
            candidates = s.list()
            stars = Stars.load(s, skill.repo, self._visitor(), similar_url(skill.repo, skill.path))
        results = find_similar(skill, candidates)
        self._send(HTTPStatus.OK, render_similar(
            skill, results, star_button=stars.button(skill, big=True), repo_count=len(entries),
        ))

    def _star(self, query: dict[str, list[str]]) -> None:
        origin = self.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc != self.headers.get("Host"):
            self._send(HTTPStatus.FORBIDDEN, render_not_found(
                "Stars can only be given from this site's own pages.",
                repo_count=len(self._repos()), title="Forbidden",
            ))
            return
        star = (query.get("star") or [""])[0]
        if star not in ("0", "1"):
            self._send(HTTPStatus.BAD_REQUEST, render_not_found(
                "star must be 1 (star) or 0 (unstar).", repo_count=len(self._repos()), title="Bad request",
            ))
            return
        skill, _ = self._stored_skill((query.get("repo") or [""])[0].strip(), (query.get("path") or [""])[0])
        if skill is None:
            return
        visitor = self._visitor()
        headers = {}
        if visitor is None:
            visitor = secrets.token_urlsafe(16)
            headers["Set-Cookie"] = (
                f"{VISITOR_COOKIE}={visitor}; Path=/; Max-Age={_VISITOR_MAX_AGE}; HttpOnly; SameSite=Lax"
            )
        with Store(self.db) as s:
            count = s.set_star(skill.repo, skill.path, visitor, star == "1")
        if "application/json" in self.headers.get("Accept", ""):
            body = json.dumps({"starred": star == "1", "stars": count})
            self._send(HTTPStatus.OK, body, content_type="application/json", headers=headers)
            return
        next_url = safe_next((query.get("next") or [""])[0]) or stored_url(skill.repo)
        self._send(HTTPStatus.SEE_OTHER, "", headers={**headers, "Location": next_url})

    def _stored_skill(self, repo_input: str, path: str) -> tuple[Skill | None, list[RepoEntry]]:
        """The stored skill at ``repo_input``/``path``; sends the 404 page and returns ``None`` if there's none."""
        entries = self._repos()
        if not repo_input or not path:
            self._send(HTTPStatus.NOT_FOUND, render_not_found("No skill given.", repo_count=len(entries)))
            return None, entries
        repo = normalize_repo_url(repo_input)
        entry = next((r for r in entries if r.repo == repo), None)
        if entry is None:
            self._send(HTTPStatus.NOT_FOUND, render_not_found(
                f"{display_repo(repo)} isn't in the catalogue yet.", repo=repo, repo_count=len(entries),
            ))
            return None, entries
        with Store(self.db) as s:
            skill = next((sk for sk in s.list(repo) if sk.path == path), None)
        if skill is None:
            self._send(HTTPStatus.NOT_FOUND, render_not_found(
                f"{path} isn't a stored skill of {display_repo(repo)}.", repo=repo, repo_count=len(entries),
            ))
        return skill, entries

    def _visitor(self) -> str | None:
        """The visitor id from the star cookie, if it has a valid one."""
        try:
            morsel = SimpleCookie(self.headers.get("Cookie", "")).get(VISITOR_COOKIE)
        except CookieError:
            return None
        if morsel is None or not _VISITOR_RE.fullmatch(morsel.value):
            return None
        return morsel.value

    def _repos(self) -> list[RepoEntry]:
        # Don't create a DB just to show an empty catalogue (--no-store must leave no file behind).
        if not self.db.exists():
            return []
        with Store(self.db) as s:
            return s.repos()

    def _send(
        self, status: HTTPStatus, body: str, *,
        content_type: str = "text/html; charset=utf-8", headers: dict[str, str] | None = None,
    ) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)


def make_server(
    host: str, port: int, db: Path | str, *, store: bool = True, allow_local: bool = False,
) -> ThreadingHTTPServer:
    handler = partial(Handler, db=Path(db), store=store, allow_local=allow_local)
    return ThreadingHTTPServer((host, port), handler)


# --- Assets (inline: the page makes no external requests) -------------------------------

_LOGO_PATHS = (
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9'
    'M12 3C9.5 5.6 8.2 8.6 8.2 12s1.3 6.4 3.8 9"/>'
)
_ICON_LOGO = (
    '<svg class="brand__mark" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"'
    f' stroke-width="1.8" stroke-linecap="round" aria-hidden="true">{_LOGO_PATHS}</svg>'
)
_ICON_LOGO_FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#5b5bd6"'
    f' stroke-width="2" stroke-linecap="round">{_LOGO_PATHS}</svg>'
)
_ICON_SEARCH = (
    '<svg class="scan__icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
    '<path d="m20 20-3.5-3.5"/></svg>'
)

_CSS = """
:root {
  color-scheme: dark;
  --bg: #0f2a1d; --surface: #153524; --surface-2: #1b3f2c; --text: #e6f0ea; --muted: #9bb3a5;
  --border: #24503a; --accent: #6fd39a; --accent-hover: #8be0ad; --accent-fg: #0b2016;
  --accent-soft: #1f4a33; --focus: rgba(111, 211, 154, .4); --shadow: none;
  --term-bg: #0f1218; --term-bar: #171b23; --term-border: #262b36; --term-fg: #d5d9e0;
  --radius: 10px;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: .92em; }
h1, h2 { letter-spacing: -.015em; line-height: 1.2; }
.wrap { max-width: 1040px; margin: 0 auto; padding: 0 16px; }
.muted { color: var(--muted); }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* top bar */
.topbar { border-bottom: 1px solid var(--border); background: var(--surface); }
.topbar__inner { display: flex; align-items: center; justify-content: space-between; height: 56px; }
.brand { display: inline-flex; align-items: center; gap: 8px; color: var(--text); text-decoration: none;
         font-weight: 650; font-size: 16px; letter-spacing: -.01em; }
.brand__mark { color: var(--accent); }
.nav-link { color: var(--muted); text-decoration: none; font-weight: 500; display: inline-flex; gap: 6px; align-items: center; }
.nav-link:hover { color: var(--text); }
.count { font-size: 12px; font-weight: 600; padding: 1px 7px; border-radius: 999px;
         background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); }

main.wrap { padding-top: 32px; padding-bottom: 48px; }

/* hero + form */
.hero { padding: 40px 0 8px; }
.hero h1 { font-size: clamp(26px, 4.2vw, 38px); margin: 0 0 12px; max-width: 18em; }
.lede { color: var(--muted); font-size: 16px; max-width: 40em; margin: 0 0 24px; }
.scan { display: flex; gap: 8px; margin-bottom: 24px; }
.scan__field { position: relative; flex: 1; min-width: 0; display: flex; align-items: center; }
.scan__icon { position: absolute; left: 13px; color: var(--muted); pointer-events: none; }
.scan input { width: 100%; height: 44px; padding: 0 40px; font: inherit; color: var(--text);
              background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
              box-shadow: var(--shadow); outline: none; transition: border-color .15s, box-shadow .15s; }
.scan--hero input { height: 52px; font-size: 16px; }
.scan input::placeholder { color: var(--muted); opacity: .8; }
.scan input:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--focus); }
.scan__kbd { position: absolute; right: 10px; font: 12px var(--mono); color: var(--muted); padding: 1px 6px;
             border: 1px solid var(--border); border-radius: 5px; background: var(--surface-2); pointer-events: none; }
.scan input:focus + .scan__kbd { display: none; }
.scan button, .btn { height: 44px; padding: 0 20px; font: inherit; font-weight: 600; border: 0; border-radius: var(--radius);
                     background: var(--accent); color: var(--accent-fg); cursor: pointer; text-decoration: none;
                     display: inline-flex; align-items: center; transition: background .15s; white-space: nowrap; }
.scan--hero button { height: 52px; padding: 0 26px; }
.scan button:hover, .btn:hover { background: var(--accent-hover); }
.scan button:focus-visible, .btn:focus-visible, a:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.scan button:disabled { opacity: .7; cursor: progress; }
.btn { height: 36px; padding: 0 14px; font-size: 14px; }
.btn--ghost { background: transparent; color: var(--text); border: 1px solid var(--border); }
.btn--ghost:hover { background: var(--surface-2); }

/* loading bar */
.progress { position: fixed; inset: 0 0 auto 0; height: 3px; overflow: hidden; visibility: hidden; z-index: 10; }
.progress::after { content: ""; position: absolute; inset: 0; width: 35%; background: var(--accent);
                   animation: slide 1.1s ease-in-out infinite; }
.is-loading .progress { visibility: visible; }
@keyframes slide { from { transform: translateX(-100%); } to { transform: translateX(300%); } }

/* terminal output: its own dark palette (not the page's green), so CLI colors read as in a terminal */
.term { background: var(--term-bg); border: 1px solid var(--term-border); border-radius: var(--radius);
        overflow: hidden; box-shadow: 0 8px 24px rgba(10, 12, 20, .12); }
.term__bar { display: flex; align-items: center; gap: 12px; padding: 0 12px; height: 40px;
             background: var(--term-bar); border-bottom: 1px solid var(--term-border); }
.term__dots { display: inline-flex; gap: 6px; flex: none; }
.term__dots i { width: 10px; height: 10px; border-radius: 50%; background: #3a404c; }
.term--failed .term__dots i:first-child { background: #f7768e; }
.term__cmd { flex: 1; min-width: 0; color: #9aa3b2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12.5px; }
.term__prompt { color: #7aa2f7; }
.term__copy { flex: none; font: 12px/1 system-ui, sans-serif; color: #c0c6d1; background: transparent;
              border: 1px solid var(--term-border); border-radius: 6px; padding: 6px 10px; cursor: pointer; }
.term__copy:hover { background: #222834; }
.term__filter { display: flex; align-items: center; gap: 8px; padding: 8px 12px; position: relative;
                background: var(--term-bar); border-bottom: 1px solid var(--term-border); color: #9aa3b2; }
.term__filter .scan__icon { position: static; flex: none; }
.term__filter-input { flex: 1; min-width: 0; height: 30px; padding: 0 10px; font: 13px var(--mono);
                       color: var(--term-fg); background: var(--term-bg); border: 1px solid var(--term-border);
                       border-radius: 6px; outline: none; }
.term__filter-input:focus { border-color: var(--accent); }
.term__filter-input::placeholder { color: #6b7280; }
.skill--hidden { display: none; }
.star { margin-left: 10px; padding: 0 8px; height: 20px; vertical-align: 1px; font: 12px/18px var(--mono);
        color: #9aa3b2; background: transparent; border: 1px solid var(--term-border); border-radius: 999px;
        cursor: pointer; }
.star::before { content: "☆ " attr(data-stars); }
.star:hover { background: #222834; color: var(--term-fg); }
.star[aria-pressed="true"] { color: #e0af68; border-color: rgba(224, 175, 104, .45); }
.star[aria-pressed="true"]::before { content: "★ " attr(data-stars); }
.star:disabled { opacity: .6; cursor: progress; }
.star:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.star--big { margin: 0; height: 36px; padding: 0 14px; font: 600 14px/34px system-ui, sans-serif; vertical-align: 0;
             color: var(--text); border-color: var(--border); border-radius: var(--radius); }
.star--big::before { content: "☆ Star · " attr(data-stars); }
.star--big[aria-pressed="true"] { color: var(--accent); border-color: var(--accent); }
.star--big[aria-pressed="true"]::before { content: "★ Starred · " attr(data-stars); }
.star--big:hover { background: var(--surface-2); color: var(--text); }
.term__empty { margin: 0; padding: 4px 20px 18px; color: var(--muted); font: 13px var(--mono); }
.output { margin: 0; padding: 18px 20px; overflow-x: auto; color: var(--term-fg); tab-size: 4;
          font: 13px/1.55 var(--mono); }
.output a { color: inherit; text-decoration: underline; text-decoration-color: rgba(158, 206, 106, .35);
            text-underline-offset: 3px; }
.output a:hover { text-decoration-color: currentColor; }
.bold { font-weight: 700; } .dim { opacity: .55; }
.red { color: #f7768e; } .green { color: #9ece6a; } .yellow { color: #e0af68; }
.blue { color: #7aa2f7; } .magenta { color: #bb9af7; } .cyan { color: #7dcfff; }

/* catalogue */
.catalogue { margin-top: 40px; }
.section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap;
                border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 8px; }
.section-head h2 { font-size: 20px; margin: 0; }
.section-head p { margin: 0; font-size: 14px; }
.note { font-size: 14px; color: var(--muted); background: var(--surface-2); border-radius: 8px; padding: 8px 12px; }
.repo-list { list-style: none; margin: 0; padding: 0; }
.repo { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 12px;
        margin: 0 -12px; border-radius: 8px; color: inherit; text-decoration: none; }
.repo:hover { background: var(--surface); box-shadow: var(--shadow); }
.repo-list li + li { border-top: 1px solid var(--border); }
.repo__title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 16px; }
.repo__owner { color: var(--muted); }
.repo__name { font-weight: 600; }
.repo__meta { display: flex; align-items: center; gap: 14px; flex: none; color: var(--muted); font-size: 13px; }
.repo__commit { color: var(--muted); }
.badge { font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 999px; background: var(--accent-soft);
         color: var(--accent); white-space: nowrap; }
.badge--zero { background: var(--surface-2); color: var(--muted); }
.badge--star { background: rgba(224, 175, 104, .14); color: #e0af68; }
.empty { border: 1px dashed var(--border); border-radius: var(--radius); padding: 28px; text-align: center; color: var(--muted); }
.empty p { margin: 4px 0; }
.empty strong { color: var(--text); }
.empty--page { padding: 48px 24px; }
.empty--page .btn { margin-top: 12px; }

/* stored repository */
.repo-head { margin: 8px 0 20px; }
.crumbs { margin: 0 0 4px; font-size: 14px; color: var(--muted); }
.crumbs a { color: var(--muted); text-decoration: none; }
.crumbs a:hover { color: var(--text); }
.repo-head h1 { font-size: 28px; margin: 0 0 8px; word-break: break-word; }
.repo-head__row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.facts { margin: 0; display: flex; align-items: center; gap: 6px 14px; flex-wrap: wrap; color: var(--muted); font-size: 14px; }
.facts code { color: var(--text); }
.actions { display: flex; gap: 8px; }

.similar { margin-top: 32px; }
.starred { margin-top: 40px; }

.footer { margin: 0; color: var(--muted); font-size: 13px; padding: 20px 0 32px; border-top: 1px solid var(--border); }

@media (max-width: 640px) {
  main.wrap { padding-top: 20px; }
  .hero { padding-top: 16px; }
  .scan { flex-direction: column; }
  .scan button { width: 100%; justify-content: center; }
  .scan__kbd { display: none; }
  .repo { flex-direction: column; align-items: flex-start; gap: 6px; }
  .repo__meta { flex-wrap: wrap; gap: 10px; }
  .output { padding: 14px; font-size: 12px; }
}
@media (prefers-reduced-motion: reduce) { .progress::after { animation-duration: 3s; } }
"""

_JS = """
(() => {
  const form = document.querySelector('.scan');
  const input = form && form.querySelector('input');
  document.addEventListener('keydown', ev => {
    const t = ev.target;
    if (ev.key === '/' && input && !(t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) {
      ev.preventDefault(); input.focus(); input.select();
    }
  });
  if (form) form.addEventListener('submit', () => {
    const b = form.querySelector('button');
    b.disabled = true; b.textContent = 'Scanning\\u2026';
    document.body.classList.add('is-loading');
  });
  window.addEventListener('pageshow', () => {
    document.body.classList.remove('is-loading');
    const b = form && form.querySelector('button');
    if (b) { b.disabled = false; b.textContent = 'Scan'; }
  });
  document.querySelectorAll('[data-filter]').forEach(input => {
    const term = input.closest('.term');
    const skills = term.querySelectorAll('.skill');
    const empty = term.querySelector('[data-filter-empty]');
    input.hidden = false;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      let visible = 0;
      skills.forEach(el => {
        const match = !q || el.dataset.name.toLowerCase().includes(q) || el.dataset.desc.toLowerCase().includes(q);
        el.classList.toggle('skill--hidden', !match);
        if (match) visible++;
      });
      if (empty) empty.hidden = visible > 0;
    });
  });
  document.querySelectorAll('[data-star]').forEach(btn => {
    if (!window.fetch) return;
    btn.addEventListener('click', async ev => {
      ev.preventDefault();
      btn.disabled = true;
      try {
        const res = await fetch(btn.formAction, { method: 'POST', headers: { Accept: 'application/json' } });
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        const url = new URL(btn.formAction);
        url.searchParams.set('star', data.starred ? '0' : '1');
        btn.formAction = url.href;
        btn.dataset.stars = data.stars;
        btn.setAttribute('aria-pressed', String(data.starred));
        btn.title = data.stars + (data.stars === 1 ? ' star' : ' stars');
        btn.disabled = false;
      } catch {
        btn.disabled = false;
        btn.form.requestSubmit(btn);  // fall back to the no-JS round trip, which shows any error page
      }
    });
  });
  document.querySelectorAll('[data-copy]').forEach(btn => {
    if (!navigator.clipboard) return;
    btn.hidden = false;
    btn.addEventListener('click', async () => {
      const pre = btn.closest('.term').querySelector('pre');
      try { await navigator.clipboard.writeText(pre.innerText); btn.textContent = 'Copied'; }
      catch { btn.textContent = 'Copy failed'; }
      setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
    });
  });
})();
"""
