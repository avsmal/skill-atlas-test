"""Integration tests for the web UI (spec/web.md): a real server, real HTTP, a local git repo."""
import html
import re
from urllib.parse import quote

import pytest

from conftest import make_repo, skill_md
from skill_atlas.cli import main
from skill_atlas.store import Store


def output_text(body: str) -> str:
    m = re.search(r'<pre class="output">(.*?)</pre>', body, re.S)
    assert m, "no output block"
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))


def scan_url(repo: str) -> str:
    return "/?repo=" + quote(repo, safe="")


def stored_url(repo: str) -> str:
    return "/stored?repo=" + quote(repo, safe="")


def similar_url(repo: str, path: str) -> str:
    return f"/similar?repo={quote(repo, safe='')}&path={quote(path, safe='')}"


def test_index_has_one_input_and_no_output(serve):
    status, body = serve()("/")
    assert status == 200
    assert len(re.findall(r"<input\b", body)) == 1
    assert 'name="repo"' in body
    assert '<pre class="output">' not in body


@pytest.mark.parametrize("q", ["/?repo=", "/?repo=%20%20"])
def test_empty_repo_is_index(serve, q):
    status, body = serve()(q)
    assert status == 200
    assert '<pre class="output">' not in body


def test_scan_output_matches_cli(serve, fixture_repo, tmp_path, capsys):
    url = fixture_repo.as_uri()
    status, body = serve()(scan_url(url))
    assert status == 200
    capsys.readouterr()  # drop the server's access log

    assert main(["scan", url, "--no-store", "--color", "never", "--db", str(tmp_path / "cli.db")]) == 0
    cli = capsys.readouterr()
    warnings = cli.err.replace("\033[1;33m", "").replace("\033[0m", "")
    assert output_text(body) == warnings + cli.out.rstrip("\n")


def test_scan_output_content(serve, fixture_repo):
    status, body = serve()(scan_url(fixture_repo.as_uri()))
    text = output_text(body)
    assert text.startswith("warning: skipping .claude/skills/broken/SKILL.md: missing YAML frontmatter\n")
    assert "2. pdf\n   description: Work with PDF files\n   path:        .claude/skills/pdf/SKILL.md" in text
    assert text.endswith("2 skill(s) found")
    # input is filled in with what was typed
    assert f'value="{html.escape(fixture_repo.as_uri())}"' in body


def test_colors_are_spans(serve, fixture_repo):
    _, body = serve()(scan_url(fixture_repo.as_uri()))
    assert '<span class="bold cyan">pdf</span>' in body
    assert '<span class="bold yellow">warning:</span>' in body
    assert "\033[" not in body


def test_no_skills(serve, tmp_path):
    repo = make_repo(tmp_path / "empty", {})
    status, body = serve()(scan_url(repo.as_uri()))
    assert status == 200
    assert output_text(body).endswith("\n\nNo skills found")


def test_skill_filter_present_when_skills(serve, fixture_repo):
    _, body = serve()(scan_url(fixture_repo.as_uri()))
    assert '<input type="search" class="term__filter-input" data-filter hidden' in body
    assert 'placeholder="Filter skills…"' in body
    assert '<span class="skill" data-name="pdf" data-desc="Work with PDF files">' in body
    assert '<span class="skill" data-name="review" data-desc="Review code carefully">' in body
    assert '<p class="term__empty" data-filter-empty hidden>No matching skills.</p>' in body
    # filtering doesn't change the plain-text output
    assert "2. pdf" in output_text(body)


def test_skill_filter_absent_without_skills(serve, tmp_path):
    repo = make_repo(tmp_path / "empty", {})
    _, body = serve()(scan_url(repo.as_uri()))
    assert '<div class="term__filter">' not in body
    assert '<p class="term__empty"' not in body
    assert '<input type="search"' not in body


def test_skill_filter_escapes_name_and_description(serve, tmp_path):
    repo = make_repo(tmp_path / "xss", {
        ".claude/skills/x/SKILL.md": skill_md("<script>alert(1)</script>", "a & <b>"),
    })
    _, body = serve()(scan_url(repo.as_uri()))
    assert 'data-name="&lt;script&gt;alert(1)&lt;/script&gt;"' in body
    assert 'data-desc="a &amp; &lt;b&gt;"' in body


def test_html_is_escaped(serve, tmp_path):
    repo = make_repo(tmp_path / "xss", {
        ".claude/skills/x/SKILL.md": skill_md("<script>alert(1)</script>", "a & <b>"),
    })
    _, body = serve()(scan_url(repo.as_uri()))
    assert "<script>alert" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "a &amp; &lt;b&gt;" in body


def test_input_is_escaped(serve):
    _, body = serve(allow_local=False)(scan_url('x"><script>alert(1)</script>'))
    assert "<script>alert" not in body
    assert 'value="x&quot;&gt;&lt;script&gt;' in body


def test_clone_failure_is_502(serve, tmp_path):
    get = serve()
    status, body = get(scan_url((tmp_path / "missing").as_uri()))
    assert status == 502
    assert output_text(body).startswith("error: ")
    assert not (tmp_path / "web.db").exists()


@pytest.mark.parametrize("repo", ["file:///etc", "git@gitlab.com:o/r.git", "--upload-pack=touch x", "/tmp/r"])
def test_non_https_rejected_by_default(serve, tmp_path, fixture_repo, repo):
    status, body = serve(allow_local=False)(scan_url(repo))
    assert status == 400
    assert output_text(body) == "error: only https:// repository URLs are accepted"
    assert not (tmp_path / "web.db").exists()


def test_local_repo_rejected_by_default(serve, tmp_path, fixture_repo):
    status, _ = serve(allow_local=False)(scan_url(fixture_repo.as_uri()))
    assert status == 400


def test_unknown_path_is_404(serve):
    status, _ = serve()("/nope")
    assert status == 404


def test_results_are_stored(serve, fixture_repo, tmp_path):
    serve()(scan_url(fixture_repo.as_uri()))
    with Store(tmp_path / "web.db") as s:
        assert sorted(x.name for x in s.list()) == ["pdf", "review"]


def test_no_store(serve, fixture_repo, tmp_path):
    status, _ = serve(store=False)(scan_url(fixture_repo.as_uri()))
    assert status == 200
    assert not (tmp_path / "web.db").exists()


def test_serve_cli_args():
    from skill_atlas.cli import build_parser

    args = build_parser().parse_args(["serve", "--port", "0", "--no-store", "--allow-local"])
    assert (args.host, args.port, args.no_store, args.allow_local) == ("127.0.0.1", 0, True, True)


@pytest.fixture
def github_repo(tmp_path, monkeypatch):
    """A local repo that git clones in place of ``https://github.com/o/r`` (url.insteadOf)."""
    repo = make_repo(tmp_path / "gh", {
        ".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files"),
        ".agents/skills/ünï code/SKILL.md": skill_md("uni", "Unicode path"),
        ".agents/skills/dup/SKILL.md": skill_md("dup", "In both"),
        ".claude/skills/dup/SKILL.md": skill_md("dup", "In both"),
    })
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{repo.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/o/r")
    return "https://github.com/o/r"


def test_paths_link_to_github(serve, github_repo):
    status, body = serve(allow_local=False)(scan_url("o/r"))
    assert status == 200
    sha = re.search(r"@</span> <span class=\"magenta\">([0-9a-f]{12})", body).group(1)
    links = re.findall(r'<a href="([^"]+)" target="_blank" rel="noopener"><span class="green">([^<]+)</span></a>', body)
    assert [text for _, text in links] == [
        ".agents/skills/dup/SKILL.md",
        ".claude/skills/dup/SKILL.md",
        ".agents/skills/ünï code/SKILL.md",
        ".claude/skills/pdf/SKILL.md",
    ]
    for href, _ in links:
        assert re.fullmatch(r"https://github\.com/o/r/blob/[0-9a-f]{40}/\S+", href)
        assert href.split("/")[6].startswith(sha)
    assert links[1][0].endswith("/.claude/skills/dup/SKILL.md")
    assert links[2][0].endswith("/.agents/skills/%C3%BCn%C3%AF%20code/SKILL.md")
    assert links[3][0].endswith("/.claude/skills/pdf/SKILL.md")
    # link text leaves the plain-text output unchanged
    text = output_text(body)
    assert "   path:        .claude/skills/pdf/SKILL.md" in text
    assert "   path:        .agents/skills/dup/SKILL.md\n                .claude/skills/dup/SKILL.md\n" in text


def test_non_github_paths_are_not_links(serve, fixture_repo):
    _, body = serve()(scan_url(fixture_repo.as_uri()))
    assert "<a href" not in body
    assert '<span class="green">.claude/skills/pdf/SKILL.md</span>' in body


# --- Catalogue and stored pages --------------------------------------------------------

def title(body: str) -> str:
    return html.unescape(re.search(r"<title>(.*?)</title>", body).group(1))


def seed(db, repo, skills, commit, scanned_at):
    from skill_atlas.models import Skill

    with Store(db) as s:
        s.replace_repo(repo, [Skill(repo, n, f"{n} skill", commit, f".claude/skills/{n}/SKILL.md") for n in skills], commit)
        s.conn.execute("UPDATE repos SET scanned_at = ? WHERE repo = ?", (scanned_at, repo))
        s.conn.commit()


def test_catalogue_lists_scanned_repos(serve, fixture_repo, tmp_path):
    get = serve()
    url = fixture_repo.as_uri()
    get(scan_url(url))
    empty = make_repo(tmp_path / "empty", {})
    get(scan_url(empty.as_uri()))

    status, body = get("/")
    assert status == 200
    assert title(body) == "skill-atlas"
    catalogue = body[body.index('id="catalogue"'):]
    assert "2 repositories · 2 skills" in catalogue
    assert f'href="/stored?repo={quote(url, safe="")}"' in catalogue
    assert '<span class="badge">2 skills</span>' in catalogue
    assert '<span class="badge badge--zero">0 skills</span>' in catalogue  # 0-skill repos are listed
    with Store(tmp_path / "web.db") as s:
        commit = s.repos()[0].commit
    assert f"<code class=\"repo__commit\">{commit[:12]}</code>" in catalogue
    assert re.search(r'<time datetime="[^"]+">\d{4}-\d\d-\d\d \d\d:\d\d UTC</time>', catalogue)
    assert '<span class="count">2</span>' in body  # top bar


def test_catalogue_order_names_and_escaping(serve, tmp_path):
    db = tmp_path / "web.db"
    seed(db, "https://github.com/acme/old", ["a"], "1" * 40, "2026-01-01T00:00:00+00:00")
    seed(db, "https://github.com/acme/new", ["a", "b", "c"], "2" * 40, "2026-03-01T00:00:00+00:00")
    seed(db, "file:///srv/<b>&x", [], "3" * 40, "2026-02-01T00:00:00+00:00")
    _, body = serve()("/")
    shown = re.findall(r'class="repo__name">([^<]+)<', body)
    assert shown == ["new", "file:///srv/&lt;b&gt;&amp;x", "old"]  # most recent first
    assert '<span class="repo__owner">acme/</span>' in body
    assert "<b>&x" not in body
    assert "3 repositories · 4 skills" in body
    assert "2026-03-01 00:00 UTC" in body


def test_catalogue_empty(serve):
    _, body = serve()("/")
    assert "No repositories yet" in body
    assert '<span class="count">0</span>' in body
    assert "--no-store" not in body


def test_catalogue_no_store_note(serve, tmp_path):
    seed(tmp_path / "web.db", "https://github.com/o/r", ["a"], "1" * 40, "2026-01-01T00:00:00+00:00")
    _, body = serve(store=False)("/")
    assert "<code>--no-store</code>: new scans are not added" in body
    assert "o/</span>" in body  # the existing DB is still shown


def test_stored_matches_cli_list(serve, fixture_repo, tmp_path, capsys):
    get = serve()
    url = fixture_repo.as_uri()
    get(scan_url(url))
    status, body = get("/stored?repo=" + quote(url, safe=""))
    assert status == 200
    capsys.readouterr()  # drop the server's access log

    assert main(["list", "--repo", url, "--color", "never", "--db", str(tmp_path / "web.db")]) == 0
    assert output_text(body) == capsys.readouterr().out.rstrip("\n")
    assert f"$</span> skill-atlas list --repo {html.escape(url)}" in body
    assert f'href="{html.escape(scan_url(url))}">Rescan</a>' in body
    assert "View on GitHub" not in body  # not a GitHub repo


def test_stored_github_repo_by_shorthand(serve, tmp_path):
    seed(tmp_path / "web.db", "https://github.com/o/r", ["pdf"], "a" * 40, "2026-01-01T00:00:00+00:00")
    status, body = serve()("/stored?repo=o/r")
    assert status == 200
    assert title(body) == "o/r · skill-atlas"
    assert "<h1>o/r</h1>" in body
    assert '<a class="btn btn--ghost" href="https://github.com/o/r" target="_blank" rel="noopener">View on GitHub</a>' in body
    assert f'href="https://github.com/o/r/blob/{"a" * 40}/.claude/skills/pdf/SKILL.md"' in body
    assert output_text(body).endswith("1 skill(s) stored")


def test_stored_zero_skill_repo(serve, tmp_path):
    seed(tmp_path / "web.db", "https://github.com/o/empty", [], "b" * 40, "2026-01-01T00:00:00+00:00")
    status, body = serve()("/stored?repo=o/empty")
    assert status == 200
    assert output_text(body) == "No skills stored"
    assert "/similar?" not in body  # no skills, so nothing to link
    assert '<input type="search"' not in body  # nothing to filter


def test_stored_page_links_names_to_similar_skills(serve, tmp_path):
    seed(tmp_path / "web.db", "https://github.com/o/r", ["pdf", "review"], "a" * 40, "2026-01-01T00:00:00+00:00")
    _, body = serve()("/stored?repo=o/r")
    for name, path in [("pdf", ".claude/skills/pdf/SKILL.md"), ("review", ".claude/skills/review/SKILL.md")]:
        href = html.escape(similar_url("https://github.com/o/r", path))
        assert f'<a href="{href}"><span class="bold cyan">{name}</span></a>' in body
    # the linked name is still the same plain text as the CLI output — no separate list
    assert output_text(body).count("Similar skills") == 0


def test_stored_skill_filter_present(serve, fixture_repo):
    get = serve()
    url = fixture_repo.as_uri()
    get(scan_url(url))
    _, body = get("/stored?repo=" + quote(url, safe=""))
    assert '<input type="search" class="term__filter-input" data-filter hidden' in body
    assert 'data-name="pdf" data-desc="Work with PDF files"' in body


def test_stored_unknown_repo_is_404(serve, tmp_path):
    seed(tmp_path / "web.db", "https://github.com/o/r", ["a"], "1" * 40, "2026-01-01T00:00:00+00:00")
    status, body = serve()("/stored?repo=o/missing")
    assert status == 404
    assert "o/missing isn&#x27;t in the catalogue yet." in body
    assert 'href="/?repo=https%3A%2F%2Fgithub.com%2Fo%2Fmissing">Scan it</a>' in body


@pytest.mark.parametrize("path", ["/stored", "/stored?repo="])
def test_stored_without_repo_is_404(serve, path):
    status, body = serve()(path)
    assert status == 404
    assert "No repository given." in body


# --- Similar skills ---------------------------------------------------------------------

def seed_skills(db, repo, skills, commit, scanned_at="2026-01-01T00:00:00+00:00"):
    with Store(db) as s:
        s.replace_repo(repo, skills, commit)
        s.conn.execute("UPDATE repos SET scanned_at = ? WHERE repo = ?", (scanned_at, repo))
        s.conn.commit()


def test_similar_shows_results_above_threshold_sorted(serve, tmp_path):
    from skill_atlas.models import Skill

    db = tmp_path / "web.db"
    target = Skill("https://github.com/o/r", "pdf", "Work with PDF files", "a" * 40,
                    ".claude/skills/pdf/SKILL.md", content="Convert PDFs to text and back.")
    close = Skill("https://github.com/o/other", "pdf2", "Work with PDF files", "b" * 40,
                   ".claude/skills/pdf2/SKILL.md", content="Convert PDFs to text.")
    # empty description/content scores 0 similarity (SequenceMatcher ratio against "" is 0), so it's excluded
    unrelated = Skill("https://github.com/o/other", "deploy", "", "b" * 40, ".claude/skills/deploy/SKILL.md")
    seed_skills(db, target.repo, [target], target.commit)
    seed_skills(db, close.repo, [close, unrelated], close.commit)

    status, body = serve()(similar_url(target.repo, target.path))
    assert status == 200
    assert title(body) == "Similar to pdf · skill-atlas"
    assert "<h1>Similar to pdf</h1>" in body
    names = re.findall(r'class="repo__name">([^<]+)<', body)
    assert names == ["pdf2"]  # unrelated is below 10%, target itself is excluded
    assert re.search(r'<span class="badge">\d+\.\d%</span>', body)
    assert f'href="{html.escape(stored_url(close.repo))}"' in body


def test_similar_no_results(serve, tmp_path):
    from skill_atlas.models import Skill

    db = tmp_path / "web.db"
    target = Skill("https://github.com/o/r", "pdf", "Work with PDF files", "a" * 40, ".claude/skills/pdf/SKILL.md")
    seed_skills(db, target.repo, [target], target.commit)
    status, body = serve()(similar_url(target.repo, target.path))
    assert status == 200
    assert "No similar skills found." in body
    assert "10%" in body


def test_similar_unknown_repo_is_404(serve, tmp_path):
    seed_skills(tmp_path / "web.db", "https://github.com/o/r", [], "a" * 40)
    status, body = serve()(similar_url("https://github.com/o/missing", ".claude/skills/x/SKILL.md"))
    assert status == 404
    assert "o/missing isn&#x27;t in the catalogue yet." in body


def test_similar_unknown_path_is_404(serve, tmp_path):
    from skill_atlas.models import Skill

    db = tmp_path / "web.db"
    seed_skills(db, "https://github.com/o/r", [Skill("https://github.com/o/r", "pdf", "d", "a" * 40,
                                                       ".claude/skills/pdf/SKILL.md")], "a" * 40)
    status, body = serve()(similar_url("https://github.com/o/r", ".claude/skills/missing/SKILL.md"))
    assert status == 404
    assert "isn&#x27;t a stored skill of o/r" in body


@pytest.mark.parametrize("path", ["/similar", "/similar?repo=o/r", "/similar?path=x"])
def test_similar_missing_params_is_404(serve, path):
    status, body = serve()(path)
    assert status == 404
    assert "No skill given." in body


def test_similar_escapes_names(serve, tmp_path):
    from skill_atlas.models import Skill

    db = tmp_path / "web.db"
    repo = "file:///srv/<b>&x"
    target = Skill(repo, "a", "shared text", "a" * 40, "SKILL.md")
    other = Skill(repo, "<script>alert(1)</script>", "shared text", "a" * 40, "other/SKILL.md")
    seed_skills(db, repo, [target, other], target.commit)
    status, body = serve()(similar_url(repo, target.path))
    assert status == 200
    assert "<script>alert" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_not_found_page(serve):
    status, body = serve()("/nope")
    assert status == 404
    assert "Page not found: /nope" in body
    assert 'href="/">Go home</a>' in body


def test_scan_page_title_and_command(serve, fixture_repo):
    _, body = serve()(scan_url(fixture_repo.as_uri()))
    assert title(body) == f"{fixture_repo.as_uri()} · skill-atlas"
    assert f"$</span> skill-atlas scan {fixture_repo.as_uri()}" in body


def test_every_page_has_the_repo_input_and_a_filter_only_with_skills(serve, fixture_repo, tmp_path):
    get = serve()
    url = fixture_repo.as_uri()
    # fixture_repo has skills, so its scan/stored pages also carry the JS-only skill filter input
    pages_with_skills = [scan_url(url), "/stored?repo=" + quote(url, safe="")]
    pages_without = [
        "/", "/stored?repo=x/y", "/nope", similar_url(url, ".claude/skills/pdf/SKILL.md"),
    ]
    for path in pages_with_skills + pages_without:
        _, body = get(path)
        expected = 2 if path in pages_with_skills else 1
        assert len(re.findall(r"<input\b", body)) == expected, path
        assert 'name="repo"' in body
        # no external assets: scripts, styles and the icon are inline
        assert not re.search(r"<script[^>]+src=|<link[^>]+stylesheet", body), path
        assert re.findall(r'<link rel="icon" href="([^"]{5})', body) == ["data:"], path


def test_background_is_dark_green_in_every_theme(serve, fixture_repo, tmp_path):
    get = serve()
    get(scan_url(fixture_repo.as_uri()))
    for path in ["/", scan_url(fixture_repo.as_uri()), stored_url(fixture_repo.as_uri()), "/nope"]:
        _, body = get(path)
        css = re.search(r"<style>(.*?)</style>", body, re.S).group(1)
        assert "--bg: #0f2a1d;" in css
        assert "color-scheme: dark;" in css
        assert "prefers-color-scheme" not in css
        assert re.search(r"body \{[^}]*background: var\(--bg\)", css)
