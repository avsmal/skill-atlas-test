"""`skill-atlas scan <owner URL>`: every repository of a GitHub organization or user (spec/cli.md).

A local HTTP server stands in for the GitHub API (``SKILL_ATLAS_GITHUB_API``), and git's
``url.<base>.insteadOf`` redirects ``https://github.com/<owner>/<name>`` clones to local repos,
so no network is used.
"""
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import make_repo, skill_md

from skill_atlas import repo as repo_mod
from skill_atlas.cli import main
from skill_atlas.repo import github_owner_url
from skill_atlas.store import Store

# owner -> list of (name, fork); repos without a local fixture fail to clone
OWNERS = {
    "acme": [("gamma", False), ("alpha", False), ("forked", True), ("Beta", False)],
    "bad": [("ok", False), ("broken", False)],
    "mixed": [("ok", False), ("vacant", False)],
    "empty": [("Beta", False)],
    "none": [],
}
REPOS = {
    "acme/alpha": {
        ".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files"),
        ".agents/skills/review/SKILL.md": skill_md("review", "Review code"),
        ".claude/skills/broken/SKILL.md": "no frontmatter\n",
    },
    "acme/Beta": {"README.md": "no skills\n"},
    "acme/gamma": {".claude/skills/lint/SKILL.md": skill_md("lint", "Lint the code")},
    "acme/forked": {".claude/skills/upstream/SKILL.md": skill_md("upstream", "From upstream")},
    "bad/ok": {".claude/skills/ok/SKILL.md": skill_md("ok", "Fine")},
    "mixed/ok": {".claude/skills/ok/SKILL.md": skill_md("ok", "Fine")},
    "empty/Beta": {"README.md": "no skills\n"},
}


class FakeGitHub:
    def __init__(self):
        self.requests: list[tuple[str, dict]] = []  # (path?query, headers)
        self.status: int | None = None  # force an error response
        self.message = ""
        self.body = None  # force a 200 response with this body


@pytest.fixture
def github(tmp_path, monkeypatch):
    """A fake GitHub API plus local clones for every repository in ``REPOS``."""
    fake = FakeGitHub()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            fake.requests.append((self.path, dict(self.headers)))
            parts = urlsplit(self.path)
            q = parse_qs(parts.query)
            segs = parts.path.strip("/").split("/")
            if fake.status:
                return self._json(fake.status, {"message": fake.message})
            if fake.body is not None:
                return self._json(200, fake.body)
            if len(segs) != 3 or segs[0] != "users" or segs[2] != "repos" or segs[1] not in OWNERS:
                return self._json(404, {"message": "Not Found"})
            per_page, page = int(q["per_page"][0]), int(q["page"][0])
            owner = segs[1]
            items = [
                {"name": n, "full_name": f"{owner}/{n}", "fork": fork}
                for n, fork in OWNERS[owner]
            ][(page - 1) * per_page:page * per_page]
            self._json(200, items)

        def _json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("SKILL_ATLAS_GITHUB_API", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    rules = {f"https://github.com/{slug}": make_repo(tmp_path / slug, files).as_uri()
             for slug, files in REPOS.items()}
    rules["https://github.com/bad/broken"] = (tmp_path / "missing").as_uri()
    vacant = tmp_path / "mixed" / "vacant"  # a repository without commits
    vacant.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=vacant, check=True)
    rules["https://github.com/mixed/vacant"] = vacant.as_uri()
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(len(rules)))
    for i, (url, local) in enumerate(rules.items()):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{i}", f"url.{local}.insteadOf")
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{i}", url)
    yield fake
    server.shutdown()
    server.server_close()


def run(capsys, *argv):
    code = main(["scan", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def single_block(capsys, repo):
    """What ``skill-atlas scan <repo>`` prints for one repository."""
    code, out, _ = run(capsys, repo, "--no-store", "--color", "never")
    assert code == 0
    return out


@pytest.mark.parametrize("url", [
    "https://github.com/acme",
    "https://github.com/acme/",
    "http://github.com/acme",
    "https://www.github.com/acme",
    "github.com/acme",
    "github.com/acme/",
    "https://github.com/orgs/acme",
    " https://github.com/orgs/acme/ ",
])
def test_owner_url_forms(url):
    assert github_owner_url(url) == "https://github.com/acme"


@pytest.mark.parametrize("url", [
    "acme", "acme/alpha", "https://github.com/acme/alpha", "github.com/acme/alpha.git",
    "git@github.com:acme/alpha.git", "https://gitlab.com/acme", "file:///tmp/acme",
])
def test_not_owner_urls(url):
    assert github_owner_url(url) is None


@pytest.mark.parametrize("url", ["https://github.com/acme", "github.com/acme/", "https://github.com/orgs/acme"])
def test_every_owner_form_scans_the_owner(github, tmp_path, capsys, url):
    code, out, _ = run(capsys, url, "--json", "--no-store", "--db", str(tmp_path / "db"))
    assert code == 0
    assert {s["repo"] for s in json.loads(out)} == {"https://github.com/acme/alpha", "https://github.com/acme/gamma"}
    assert github.requests[0][0].startswith("/users/acme/repos?type=owner&sort=full_name&per_page=100&page=1")


def test_repository_url_is_not_an_owner_scan(github, tmp_path, capsys):
    code, out, _ = run(capsys, "https://github.com/acme/alpha", "--json", "--no-store")
    assert code == 0
    assert {s["repo"] for s in json.loads(out)} == {"https://github.com/acme/alpha"}
    assert github.requests == []


def test_text_output(github, tmp_path, capsys):
    alpha = single_block(capsys, "https://github.com/acme/alpha")
    gamma = single_block(capsys, "https://github.com/acme/gamma")
    code, out, _ = run(capsys, "https://github.com/acme", "--no-store", "--color", "never")
    assert code == 0
    # name order (case-insensitive), the fork skipped, the 0-skill repository (Beta) not printed
    assert out == (
        "https://github.com/acme: 3 repositories (1 fork skipped)\n\n"
        f"{alpha}\n{gamma}\n"
        "3 skill(s) found in 2 of 3 repositories\n"
    )


def test_text_output_colors(github, capsys):
    code, out, _ = run(capsys, "https://github.com/acme", "--no-store", "--color", "always")
    assert code == 0
    assert out.startswith("\033[1;34mhttps://github.com/acme\033[0m: 3 repositories\033[2m (1 fork skipped)\033[0m\n")
    assert out.endswith("\033[1;32m3 skill(s) found in 2 of 3 repositories\033[0m\n")


def test_no_skills_in_any_repository(github, capsys):
    code, out, _ = run(capsys, "https://github.com/empty", "--no-store", "--color", "never")
    assert code == 0
    assert out == "https://github.com/empty: 1 repository\n\nNo skills found in 1 repository\n"


def test_owner_without_repositories(github, tmp_path, capsys):
    db = tmp_path / "db"
    code, out, _ = run(capsys, "https://github.com/none", "--color", "never", "--db", str(db))
    assert code == 0
    assert out == "https://github.com/none: 0 repositories\n\nNo skills found in 0 repositories\n"


def test_json_is_a_flat_array_in_repository_order(github, capsys):
    code, out, _ = run(capsys, "https://github.com/acme", "--json", "--no-store")
    assert code == 0
    skills = json.loads(out)
    assert [(s["repo"], s["name"]) for s in skills] == [
        ("https://github.com/acme/alpha", "review"),
        ("https://github.com/acme/alpha", "pdf"),
        ("https://github.com/acme/gamma", "lint"),
    ]
    _, single, _ = run(capsys, "https://github.com/acme/alpha", "--json", "--no-store")
    assert skills[:2] == json.loads(single)


def test_warnings_name_the_repository(github, capsys):
    _, _, err = run(capsys, "https://github.com/acme", "--no-store", "--color", "never")
    assert err == (
        "warning: https://github.com/acme/alpha: skipping .claude/skills/broken/SKILL.md: "
        "missing YAML frontmatter\n"
    )


def test_every_repository_is_stored(github, tmp_path, capsys):
    db = tmp_path / "db"
    code, _, _ = run(capsys, "https://github.com/acme", "--db", str(db))
    assert code == 0
    with Store(db) as store:
        repos = {e.repo: e.skills for e in store.repos()}
        names = sorted(s.name for s in store.list())
    assert repos == {
        "https://github.com/acme/alpha": 2,
        "https://github.com/acme/Beta": 0,
        "https://github.com/acme/gamma": 1,
    }
    assert names == ["lint", "pdf", "review"]

    # rescanning replaces, never duplicates
    assert run(capsys, "https://github.com/acme", "--db", str(db))[0] == 0
    with Store(db) as store:
        assert len(store.list()) == 3


def test_no_store(github, tmp_path, capsys):
    db = tmp_path / "db"
    assert run(capsys, "https://github.com/acme", "--no-store", "--db", str(db))[0] == 0
    assert not db.exists()


def test_include_forks(github, tmp_path, capsys):
    code, out, _ = run(capsys, "https://github.com/acme", "--include-forks", "--no-store", "--color", "never")
    assert code == 0
    assert out.startswith("https://github.com/acme: 4 repositories\n\n")
    assert "https://github.com/acme/forked @ " in out
    assert out.endswith("4 skill(s) found in 3 of 4 repositories\n")


def test_pagination(github, monkeypatch, capsys):
    monkeypatch.setattr(repo_mod, "PER_PAGE", 2)
    code, out, _ = run(capsys, "https://github.com/acme", "--json", "--no-store", "--include-forks")
    assert code == 0
    assert len({s["repo"] for s in json.loads(out)}) == 3
    pages = [parse_qs(urlsplit(path).query)["page"][0] for path, _ in github.requests]
    assert pages == ["1", "2", "3"]  # 2 + 2 + 0 entries: a short page ends the listing


def test_failing_repository_does_not_stop_the_run(github, tmp_path, capsys):
    db = tmp_path / "db"
    code, out, err = run(capsys, "https://github.com/bad", "--color", "never", "--db", str(db))
    assert code == 1
    assert err.startswith("error: https://github.com/bad/broken: ")
    assert "https://github.com/bad/ok @ " in out
    assert out.endswith("1 skill(s) found in 1 of 2 repositories (1 failed)\n")
    with Store(db) as store:
        assert [e.repo for e in store.repos()] == ["https://github.com/bad/ok"]


def test_empty_repository_is_skipped_with_a_warning(github, tmp_path, capsys):
    db = tmp_path / "db"
    code, out, err = run(capsys, "https://github.com/mixed", "--color", "never", "--db", str(db))
    assert code == 0
    assert err == "warning: https://github.com/mixed/vacant: skipping: repository is empty\n"
    assert out.endswith("1 skill(s) found in 1 of 2 repositories\n")
    with Store(db) as store:
        assert [e.repo for e in store.repos()] == ["https://github.com/mixed/ok"]


def test_unknown_owner(github, tmp_path, capsys):
    db = tmp_path / "db"
    code, out, err = run(capsys, "https://github.com/nobody", "--db", str(db))
    assert code == 1
    assert out == ""
    assert err == "error: GitHub user or organization not found: nobody\n"
    assert not db.exists()


def test_api_rate_limit(github, tmp_path, capsys):
    github.status, github.message = 403, "API rate limit exceeded for 1.2.3.4."
    db = tmp_path / "db"
    code, _, err = run(capsys, "https://github.com/acme", "--db", str(db))
    assert code == 1
    assert err == (
        "error: GitHub API: HTTP 403: API rate limit exceeded for 1.2.3.4. "
        "(set GITHUB_TOKEN to raise the limit)\n"
    )
    assert not db.exists()


def test_api_server_error(github, capsys):
    github.status, github.message = 500, "Server Error"
    code, _, err = run(capsys, "https://github.com/acme", "--no-store")
    assert code == 1
    assert err == "error: GitHub API: HTTP 500: Server Error\n"


def test_api_unexpected_response(github, capsys):
    github.body = {"message": "not a list"}
    code, _, err = run(capsys, "https://github.com/acme", "--no-store")
    assert code == 1
    assert err == "error: GitHub API: unexpected response (not a list of repositories)\n"


def test_api_unreachable(github, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SKILL_ATLAS_GITHUB_API", "http://127.0.0.1:1")
    code, _, err = run(capsys, "https://github.com/acme", "--db", str(tmp_path / "db"))
    assert code == 1
    assert err.startswith("error: GitHub API: ")
    assert not (tmp_path / "db").exists()


def test_github_token_is_sent(github, monkeypatch, capsys):
    run(capsys, "https://github.com/acme", "--no-store")
    assert all("Authorization" not in headers for _, headers in github.requests)
    github.requests.clear()
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    assert run(capsys, "https://github.com/acme", "--no-store")[0] == 0
    assert [headers["Authorization"] for _, headers in github.requests] == ["Bearer t0ken"]


def test_ref_is_rejected(github, tmp_path, capsys):
    code, out, err = run(capsys, "https://github.com/acme", "--ref", "main", "--db", str(tmp_path / "db"))
    assert code == 2
    assert (out, err) == ("", "error: --ref can't be used with an organization URL\n")
    assert github.requests == []
    assert not (tmp_path / "db").exists()


def test_jobs_do_not_change_the_output(github, capsys):
    outputs = {
        jobs: run(capsys, "https://github.com/acme", "--no-store", "--color", "never", "--include-forks", *jobs)
        for jobs in [(), ("--jobs", "1"), ("--jobs", "8")]
    }
    assert len(set(outputs.values())) == 1
    assert outputs[()][0] == 0


@pytest.mark.parametrize("jobs", ["0", "-1", "x"])
def test_jobs_must_be_positive(jobs, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["scan", "https://github.com/acme", "--jobs", jobs])
    assert exc.value.code == 2


def test_interrupt_does_not_clone_queued_repositories(github, monkeypatch, tmp_path, capsys):
    import skill_atlas.cli as cli

    started = []
    real = cli._scan_collecting

    def scan(repo):
        started.append(repo)
        if len(started) == 2:
            raise KeyboardInterrupt
        return real(repo)

    monkeypatch.setattr(cli, "_scan_collecting", scan)
    db = tmp_path / "db"
    with pytest.raises(KeyboardInterrupt):
        main(["scan", "https://github.com/acme", "--include-forks", "--jobs", "1", "--db", str(db)])
    # alpha was scanned and stored, Beta was interrupted; forked and gamma never started
    # (one more may have been picked up by the worker before the queue was cancelled)
    assert started[:2] == ["https://github.com/acme/alpha", "https://github.com/acme/Beta"]
    assert len(started) <= 3
    with Store(db) as store:
        assert [e.repo for e in store.repos()] == ["https://github.com/acme/alpha"]
