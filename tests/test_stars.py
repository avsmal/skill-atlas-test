"""Integration tests for starring skills in the web UI (spec/web.md › Stars)."""
import html
import json
import re
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

from conftest import make_repo, skill_md
from skill_atlas.models import Skill
from skill_atlas.store import Store
from skill_atlas.web import VISITOR_COOKIE

REPO = "https://github.com/o/r"
COMMIT = "a" * 40


def path_of(name):
    return f".claude/skills/{name}/SKILL.md"


def seed(db, repo=REPO, names=("pdf", "review")):
    with Store(db) as s:
        s.replace_repo(repo, [Skill(repo, n, f"{n} skill", COMMIT, path_of(n)) for n in names], COMMIT)


def star_path(repo=REPO, name="pdf", star="1", next_url=None):
    url = f"/star?repo={quote(repo, safe='')}&path={quote(path_of(name), safe='')}&star={star}"
    return url if next_url is None else url + "&next=" + quote(next_url, safe="")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post(base, path, *, cookie=None, headers=None):
    """POST without following redirects; returns ``(status, headers, body)``."""
    req = urllib.request.Request(base + path, method="POST", headers=dict(headers or {}))
    if cookie:
        req.add_header("Cookie", f"{VISITOR_COOKIE}={cookie}")
    try:
        with urllib.request.build_opener(NoRedirect).open(req) as r:
            return r.status, r.headers, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode()


def get(base, path, cookie=None):
    req = urllib.request.Request(base + path)
    if cookie:
        req.add_header("Cookie", f"{VISITOR_COOKIE}={cookie}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def visitor_from(headers):
    m = re.match(rf"{VISITOR_COOKIE}=([A-Za-z0-9_-]{{22}}); ", headers["Set-Cookie"] or "")
    assert m, headers["Set-Cookie"]
    return m.group(1)


def star_buttons(body):
    """``name -> (data-stars, aria-pressed, formaction)`` for every star button on the page."""
    return {
        m["name"]: (int(m["stars"]), m["pressed"] == "true", html.unescape(m["action"]))
        for m in re.finditer(
            r'<button type="submit" class="star[^"]*" form="star-form" formaction="(?P<action>[^"]+)" data-star'
            r' data-stars="(?P<stars>\d+)" aria-pressed="(?P<pressed>true|false)" aria-label="Star (?P<name>[^"]*)"',
            body,
        )
    }


def output_text(body):
    m = re.search(r'<pre class="output">(.*?)</pre>', body, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))


def stored_url(repo=REPO):
    return "/stored?repo=" + quote(repo, safe="")


def similar_url(repo=REPO, name="pdf"):
    return f"/similar?repo={quote(repo, safe='')}&path={quote(path_of(name), safe='')}"


@pytest.fixture
def base(serve, tmp_path):
    seed(tmp_path / "web.db")
    return serve().base


def test_stored_page_has_a_star_button_per_skill(base):
    status, body = get(base, stored_url())
    assert status == 200
    buttons = star_buttons(body)
    assert set(buttons) == {"pdf", "review"}
    assert buttons["pdf"][:2] == (0, False)
    assert buttons["pdf"][2] == star_path(next_url=stored_url())
    # the buttons sit in the <pre> right after the name, but add no text to it
    pre = re.search(r'<pre class="output">(.*?)</pre>', body, re.S).group(1)
    assert re.search(r'<span class="bold cyan">pdf</span></a><button type="submit" class="star"', pre)
    assert "1. pdf\n   description: pdf skill" in output_text(body)
    assert '<form id="star-form" method="post" action="/star" hidden></form>' in body
    assert len(re.findall(r"<input\b", body)) == 2  # still just the repository URL and the filter


def test_star_without_js_sets_cookie_and_redirects_back(base, tmp_path):
    status, headers, _ = post(base, star_path(next_url=stored_url()), headers={"Origin": base})
    assert status == 303
    assert headers["Location"] == stored_url()
    cookie = headers["Set-Cookie"]
    visitor = visitor_from(headers)
    assert "Path=/" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Max-Age=" in cookie
    with Store(tmp_path / "web.db") as s:
        assert s.starred_by(visitor) == {(REPO, path_of("pdf"))}

    # the visitor sees it pressed, with an unstar action; others see the count only
    buttons = star_buttons(get(base, stored_url(), cookie=visitor)[1])
    assert buttons["pdf"] == (1, True, star_path(star="0", next_url=stored_url()))
    assert buttons["review"][:2] == (0, False)
    assert star_buttons(get(base, stored_url())[1])["pdf"][:2] == (1, False)


def test_star_counts_people_once_each_and_unstar(base):
    _, headers, _ = post(base, star_path())
    alice = visitor_from(headers)
    status, headers, _ = post(base, star_path(), cookie=alice)  # same person again: still one star
    assert status == 303 and headers["Set-Cookie"] is None  # known visitor keeps their cookie
    _, headers, _ = post(base, star_path())
    bob = visitor_from(headers)
    assert bob != alice
    assert star_buttons(get(base, stored_url())[1])["pdf"][0] == 2
    post(base, star_path(star="0"), cookie=alice)
    post(base, star_path(star="0"), cookie=alice)  # unstarring twice is a no-op
    buttons = star_buttons(get(base, stored_url(), cookie=alice)[1])
    assert buttons["pdf"][:2] == (1, False)


def test_star_json_response(base):
    status, headers, body = post(base, star_path(), headers={"Accept": "application/json"})
    assert status == 200
    assert headers["Content-Type"] == "application/json"
    assert json.loads(body) == {"starred": True, "stars": 1}
    visitor = visitor_from(headers)  # the cookie is set on the JSON response too
    status, _, body = post(base, star_path(star="0"), cookie=visitor, headers={"Accept": "application/json"})
    assert json.loads(body) == {"starred": False, "stars": 0}


def test_star_from_another_site_is_403(base, tmp_path):
    status, headers, body = post(base, star_path(), headers={"Origin": "https://evil.example"})
    assert status == 403
    assert "Stars can only be given from this site" in body
    assert headers["Set-Cookie"] is None
    with Store(tmp_path / "web.db") as s:
        assert s.star_counts() == {}


@pytest.mark.parametrize("star", ["", "2", "yes"])
def test_star_needs_star_0_or_1(base, tmp_path, star):
    path = star_path(star=star) if star else star_path().replace("&star=1", "")
    status, _, body = post(base, path)
    assert status == 400
    assert "star must be 1 (star) or 0 (unstar)." in body
    with Store(tmp_path / "web.db") as s:
        assert s.star_counts() == {}


@pytest.mark.parametrize("path", [
    star_path(repo="https://github.com/o/missing"),
    star_path(name="missing"),
    "/star?star=1",
    f"/star?repo={quote(REPO, safe='')}&star=1",
])
def test_star_unknown_skill_is_404(base, tmp_path, path):
    status, _, body = post(base, path)
    assert status == 404
    assert "Not found · skill-atlas" in body
    with Store(tmp_path / "web.db") as s:
        assert s.star_counts() == {}


def test_star_accepts_repo_shorthand(base):
    status, _, _ = post(base, star_path(repo="o/r"))
    assert status == 303
    assert star_buttons(get(base, stored_url())[1])["pdf"][0] == 1


@pytest.mark.parametrize("next_url", [
    None, "", "//evil.example/", "https://evil.example/", "/\\evil.example", "/x\r\nSet-Cookie: a=b", "stored",
])
def test_star_redirect_stays_on_this_site(base, next_url):
    status, headers, _ = post(base, star_path(next_url=next_url))
    assert status == 303
    assert headers["Location"] == stored_url()


def test_invalid_cookie_is_a_new_visitor(base):
    status, headers, _ = post(base, star_path(), cookie="not-a-valid-id")
    assert status == 303
    visitor_from(headers)  # replaced with a fresh id


def test_get_star_and_other_posts_are_404(base):
    assert get(base, star_path())[0] == 404
    assert post(base, "/stored?repo=o/r")[0] == 404


def test_similar_page_has_a_big_star_button(base):
    _, headers, _ = post(base, star_path())
    visitor = visitor_from(headers)
    status, body = get(base, similar_url(), cookie=visitor)
    assert status == 200
    assert 'class="star star--big"' in body
    assert star_buttons(body) == {"pdf": (1, True, star_path(star="0", next_url=similar_url()))}
    status, headers, _ = post(base, star_buttons(body)["pdf"][2], cookie=visitor)
    assert headers["Location"] == similar_url()


def test_scan_page_has_star_buttons_when_stored(serve, tmp_path):
    repo = make_repo(tmp_path / "src", {".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files")})
    url = repo.as_uri()
    _, body = serve()("/?repo=" + quote(url, safe=""))
    buttons = star_buttons(body)
    assert buttons["pdf"] == (0, False, star_path(repo=url, next_url=stored_url(url)))
    assert output_text(body).endswith("1. pdf\n   description: Work with PDF files\n"
                                      "   path:        .claude/skills/pdf/SKILL.md\n\n1 skill(s) found")


def test_scan_page_has_no_star_buttons_with_no_store(serve, tmp_path):
    repo = make_repo(tmp_path / "src", {".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files")})
    _, body = serve(store=False)("/?repo=" + quote(repo.as_uri(), safe=""))
    assert star_buttons(body) == {}
    assert "1. pdf" in output_text(body)


def test_stars_survive_a_rescan(serve, tmp_path):
    repo = make_repo(tmp_path / "src", {".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files")})
    url = repo.as_uri()
    get_ = serve()
    get_("/?repo=" + quote(url, safe=""))
    post(get_.base, star_path(repo=url))
    _, body = get_("/?repo=" + quote(url, safe=""))  # rescan
    assert star_buttons(body)["pdf"][0] == 1


def test_home_most_starred(serve, tmp_path):
    db = tmp_path / "web.db"
    seed(db)
    seed(db, "https://github.com/acme/tools", ["<b>lint</b>"])
    base = serve().base
    _, body = get(base, "/")
    assert "Most starred" not in body  # nothing starred yet

    def star_by(n, repo, name):
        for _ in range(n):
            post(base, f"/star?repo={quote(repo, safe='')}&path={quote(path_of(name), safe='')}&star=1")

    star_by(1, REPO, "review")
    star_by(2, "https://github.com/acme/tools", "<b>lint</b>")
    star_by(1, REPO, "pdf")
    _, body = get(base, "/")
    section = body[body.index('id="starred"'):body.index('id="catalogue"')]
    names = re.findall(r'class="repo__name">([^<]+)<', section)
    assert names == ["&lt;b&gt;lint&lt;/b&gt;", "pdf", "review"]  # most stars first, then repo and name
    assert '<span class="badge badge--star">★ 2</span>' in section
    assert f'href="{html.escape(similar_url(name="pdf"))}"' in section
    assert '<span class="muted">acme/tools</span>' in section
    assert len(re.findall(r"<input\b", body)) == 1


def test_home_most_starred_hides_skills_gone_upstream(serve, tmp_path):
    db = tmp_path / "web.db"
    seed(db)
    base = serve().base
    post(base, star_path())
    seed(db, names=("review",))  # pdf was deleted upstream
    _, body = get(base, "/")
    assert "Most starred" not in body
