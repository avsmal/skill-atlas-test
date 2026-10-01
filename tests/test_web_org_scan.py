"""Scanning an organization or user from the web UI (spec/web.md › Scanning an organization).

Uses the fake GitHub API and the ``insteadOf`` clone redirects of ``test_org_scan.py``, so no
network is used.
"""
import html
import re
import socket
import threading
import time
from urllib.parse import parse_qs, urlsplit

import pytest

from skill_atlas import cli
from skill_atlas.cli import main
from skill_atlas.store import Store
from test_org_scan import OWNERS, github  # noqa: F401 (pytest fixture)
from test_web import output_text, scan_url, stored_url

ACME = "https://github.com/acme"
ALPHA, GAMMA = f"{ACME}/alpha", f"{ACME}/gamma"


def cli_output(capsys, tmp_path, owner):
    """``skill-atlas scan <owner> --no-store --color never``: (stdout without the last newline, stderr)."""
    capsys.readouterr()  # drop the server's access log
    main(["scan", owner, "--no-store", "--color", "never", "--db", str(tmp_path / "cli.db")])
    out = capsys.readouterr()
    return out.out.rstrip("\n"), out.err.replace("\033[1;33m", "").replace("\033[1;31m", "").replace("\033[0m", "")


def without_diagnostics(text):
    return "\n".join(line for line in text.split("\n") if not line.startswith(("warning: ", "error: ")))


@pytest.mark.parametrize("allow_local", [False, True])
@pytest.mark.parametrize("url", [ACME, "github.com/acme/", "https://github.com/orgs/acme"])
def test_owner_url_is_scanned(github, serve, url, allow_local):
    status, body = serve(allow_local=allow_local)(scan_url(url))
    assert status == 200
    text = output_text(body)
    assert text.startswith(f"{ACME}: 3 repositories (1 fork skipped)\n")
    assert text.endswith("\n3 skill(s) found in 2 of 3 repositories")
    assert github.requests[0][0].startswith("/users/acme/repos?type=owner&sort=full_name&per_page=100&page=1")


def test_output_matches_cli(github, serve, tmp_path, capsys):
    status, body = serve()(scan_url(ACME))
    assert status == 200
    out, err = cli_output(capsys, tmp_path, ACME)
    text = output_text(body)
    assert without_diagnostics(text) == out
    # the warning comes right before its repository's block, as on a terminal (2>&1)
    warning = err.rstrip("\n")
    assert warning.startswith(f"warning: {ALPHA}: skipping .claude/skills/broken/SKILL.md")
    assert text.split("\n")[1] == warning
    assert text.split("\n")[2:4] == ["", f"{ALPHA} @ " + text.split(" @ ")[1].split("\n")[0]]


def test_page(github, serve):
    status, body = serve()(scan_url(ACME))
    assert "<title>acme · skill-atlas</title>" in body
    assert "<span class=\"term__prompt\">$</span> skill-atlas scan https://github.com/acme</code>" in body
    assert len(re.findall(r'<input name="repo"', body)) == 1
    assert f'value="{ACME}"' in body
    assert '<span class="bold blue">https://github.com/acme</span>' in body  # colors, as in a single scan
    assert body.rstrip().endswith("</html>")


def test_skills_link_to_github_and_have_the_filter(github, serve):
    _, body = serve()(scan_url(ACME))
    assert re.search(rf'href="{GAMMA}/blob/[0-9a-f]{{40}}/\.claude/skills/lint/SKILL\.md" target="_blank"', body)
    assert len(re.findall(r'<span class="skill" data-name=', body)) == 3
    assert 'data-name="lint" data-desc="Lint the code"' in body
    assert re.search(r"<input [^>]*data-filter hidden", body)


@pytest.mark.parametrize("owner", ["empty", "none"])
def test_filter_field_is_there_even_without_skills(github, serve, owner):
    # the page starts before any skill is found; the script only unhides the field if one is
    status, body = serve()(scan_url(f"https://github.com/{owner}"))
    assert status == 200
    assert re.search(r"<input [^>]*data-filter hidden", body)
    assert "if (!skills.length) return;" in body
    assert output_text(body).endswith(" repository" if owner == "empty" else " repositories")


def test_progress_ticks_add_no_text(github, serve):
    _, body = serve()(scan_url(ACME))
    pre = re.search(r'<pre class="output">(.*?)</pre>', body, re.S).group(1)
    ticks = re.findall(r'<i class="tick" data-done="(\d+)" data-total="3"></i>', pre)
    assert ticks == ["0", "1", "2", "3"]
    assert pre.endswith('<i class="tick tick--done"></i>')
    assert ".output .tick:last-of-type:not(.tick--done)::after" in body


def test_every_repository_is_stored(github, serve, tmp_path):
    get = serve()
    assert get(scan_url(ACME))[0] == 200
    with Store(tmp_path / "web.db") as store:
        assert {e.repo: e.skills for e in store.repos()} == {ALPHA: 2, f"{ACME}/Beta": 0, GAMMA: 1}
    _, home = get("/")
    assert "3 repositories · 3 skills" in home
    status, stored = get(stored_url(GAMMA))
    assert status == 200 and "lint" in output_text(stored)


def test_no_store(github, serve, tmp_path):
    status, body = serve(store=False)(scan_url(ACME))
    assert status == 200
    assert "3 skill(s) found in 2 of 3 repositories" in output_text(body)
    assert "data-star" not in re.search(r'<pre class="output">(.*?)</pre>', body, re.S).group(1)
    assert not (tmp_path / "web.db").exists()


def test_star_buttons_return_to_each_repositorys_stored_page(github, serve):
    _, body = serve()(scan_url(ACME))
    actions = {
        name: parse_qs(urlsplit(html.unescape(action)).query)
        for action, name in re.findall(r'formaction="([^"]+)" data-star[^>]* aria-label="Star ([^"]+)"', body)
    }
    assert set(actions) == {"pdf", "review", "lint"}
    assert actions["pdf"]["repo"] == [ALPHA] and actions["pdf"]["next"] == [stored_url(ALPHA)]
    assert actions["lint"]["repo"] == [GAMMA] and actions["lint"]["next"] == [stored_url(GAMMA)]


def test_stars_are_shown(github, serve, tmp_path):
    get = serve()
    get(scan_url(ACME))
    with Store(tmp_path / "web.db") as store:
        path = next(s.path for s in store.list(GAMMA))
        store.set_star(GAMMA, path, "v" * 22, True)
    _, body = get(scan_url(ACME))
    assert re.search(r'data-stars="1" aria-pressed="false" aria-label="Star lint"', body)


def test_failing_repository_does_not_stop_the_scan(github, serve, tmp_path, capsys):
    status, body = serve()(scan_url("https://github.com/bad"))
    assert status == 200
    text = output_text(body)
    assert "\nerror: https://github.com/bad/broken: " in text
    assert text.endswith("\n1 skill(s) found in 1 of 2 repositories (1 failed)")
    out, err = cli_output(capsys, tmp_path, "https://github.com/bad")
    assert err.startswith("error: https://github.com/bad/broken: ")
    assert text.replace("\n" + err.rstrip("\n"), "") == out  # git's message may span several lines
    with Store(tmp_path / "web.db") as store:
        assert [e.repo for e in store.repos()] == ["https://github.com/bad/ok"]


def test_empty_repository_is_a_warning(github, serve):
    status, body = serve()(scan_url("https://github.com/mixed"))
    assert status == 200
    text = output_text(body)
    assert "\nwarning: https://github.com/mixed/vacant: skipping: repository is empty" in text
    assert text.endswith("\n1 skill(s) found in 1 of 2 repositories")


def test_unknown_owner(github, serve, tmp_path):
    status, body = serve()(scan_url("https://github.com/nobody"))
    assert status == 502
    assert output_text(body) == "error: GitHub user or organization not found: nobody"
    assert 'class="term term--failed"' in body
    assert not (tmp_path / "web.db").exists()


def test_api_error(github, serve, tmp_path):
    github.status, github.message = 403, "API rate limit exceeded for 1.2.3.4."
    status, body = serve()(scan_url(ACME))
    assert status == 502
    assert output_text(body) == (
        "error: GitHub API: HTTP 403: API rate limit exceeded for 1.2.3.4. (set GITHUB_TOKEN to raise the limit)"
    )
    assert not (tmp_path / "web.db").exists()


def raw_get(base, path):
    """Send a GET on a raw socket; return the connected socket."""
    host, port = urlsplit(base).netloc.split(":")
    sock = socket.create_connection((host, int(port)), timeout=10)
    sock.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
    return sock


def read_until(sock, marker: bytes) -> bytes:
    data = b""
    while marker not in data:
        chunk = sock.recv(65536)
        assert chunk, f"connection closed before {marker!r}"
        data += chunk
    return data


def test_output_is_streamed(github, serve, monkeypatch):
    release = threading.Event()
    real = cli._scan_collecting

    def scan(repo):
        if repo == GAMMA:
            assert release.wait(10)
        return real(repo)

    monkeypatch.setattr(cli, "_scan_collecting", scan)
    sock = raw_get(serve().base, scan_url(ACME))
    try:
        # alpha's block arrives while gamma is still scanning
        data = read_until(sock, b"2 skill(s) found")
        head = data.split(b"\r\n\r\n", 1)[0].decode()
        assert head.startswith("HTTP/1.0 200")
        assert "Content-Length" not in head and "Cache-Control: no-store" in head
        assert b"1 skill(s) found" not in data and b"</html>" not in data
        release.set()
        data += read_until(sock, b"</html>")
        assert b"3 skill(s) found in 2 of 3 repositories" in data
    finally:
        release.set()
        sock.close()


def test_leaving_the_page_cancels_queued_repositories(github, serve, monkeypatch):
    names = [f"r{i:02}" for i in range(40)]
    monkeypatch.setitem(OWNERS, "many", [(n, False) for n in names])
    started = []

    def scan(repo):
        started.append(repo)
        time.sleep(0.2)
        return repo, None, [], [], "clone failed"

    monkeypatch.setattr(cli, "_scan_collecting", scan)
    sock = raw_get(serve().base, scan_url("https://github.com/many"))
    read_until(sock, b'data-done="1"')
    sock.close()
    # wait for the scan to stop: two ticks' worth of time with nothing new started
    count = -1
    while count != len(started):
        count = len(started)
        time.sleep(0.5)
    assert len(started) < 20, started
