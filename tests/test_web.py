"""Integration tests for the web UI (spec/web.md): a real server, real HTTP, a local git repo."""
import html
import re
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

from conftest import make_repo, skill_md
from skill_atlas.cli import main
from skill_atlas.store import Store
from skill_atlas.web import make_server


@pytest.fixture
def serve(tmp_path):
    """Start a server; returns ``get(path) -> (status, body)``."""
    servers = []

    def start(**kwargs):
        kwargs.setdefault("allow_local", True)
        server = make_server("127.0.0.1", 0, tmp_path / "web.db", **kwargs)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def get(path):
            try:
                with urllib.request.urlopen(base + path) as r:
                    return r.status, r.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()
        return get

    yield start
    for s in servers:
        s.shutdown()
        s.server_close()


def output_text(body: str) -> str:
    m = re.search(r'<pre class="output">(.*?)</pre>', body, re.S)
    assert m, "no output block"
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))


def scan_url(repo: str) -> str:
    return "/?repo=" + quote(repo, safe="")


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
    assert [text for _, text in links] == [".agents/skills/ünï code/SKILL.md", ".claude/skills/pdf/SKILL.md"]
    for href, _ in links:
        assert re.fullmatch(r"https://github\.com/o/r/blob/[0-9a-f]{40}/\S+", href)
        assert href.split("/")[6].startswith(sha)
    assert links[0][0].endswith("/.agents/skills/%C3%BCn%C3%AF%20code/SKILL.md")
    assert links[1][0].endswith("/.claude/skills/pdf/SKILL.md")
    # link text leaves the plain-text output unchanged
    assert "   path:        .claude/skills/pdf/SKILL.md" in output_text(body)


def test_non_github_paths_are_not_links(serve, fixture_repo):
    _, body = serve()(scan_url(fixture_repo.as_uri()))
    assert "<a href" not in body
    assert '<span class="green">.claude/skills/pdf/SKILL.md</span>' in body
