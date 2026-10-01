"""Repository URL handling and shallow cloning."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_GITHUB_REPO = re.compile(r"^https://github\.com/([\w.-]+/[\w.-]+)$")
_SHORTHAND = re.compile(r"^[\w.-]+/[\w.-]+$")
_GITHUB_OWNER = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?:orgs/)?([\w.-]+)$")
# GitHub REST API page size (its maximum); a shorter page is the last one.
PER_PAGE = 100
# gitignore-style patterns (non-cone sparse checkout) for rule (a) in spec/cli.md:
# <prefix>/.agents|.claude/skills/<skill-dir>/SKILL.md, file name in any case.
_SKILL_FILE_GLOB = "[Ss][Kk][Ii][Ll][Ll].[Mm][Dd]"
SPARSE_PATTERNS = [f"**/{d}/skills/*/{_SKILL_FILE_GLOB}" for d in (".agents", ".claude")]
# Never run Git LFS filters: skill files are plain text and git-lfs may be absent.
_NO_LFS = ["-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=", "-c", "filter.lfs.required=false"]


class RepoError(Exception):
    pass


class EmptyRepoError(RepoError):
    """The repository has no commits."""


def normalize_repo_url(url: str) -> str:
    """Return a canonical repository URL.

    Accepts ``owner/repo``, ``github.com/owner/repo``, ``.git`` suffixes and
    trailing slashes. Non-GitHub URLs (e.g. ``file://``) are returned stripped.
    """
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if _SHORTHAND.match(url):
        return f"https://github.com/{url}"
    if url.startswith("github.com/"):
        url = "https://" + url
    m = re.match(r"^(?:https?://|git@)(?:www\.)?github\.com[:/]([\w.-]+)/([\w.-]+)", url)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}"
    return url


def github_owner_url(url: str) -> str | None:
    """``https://github.com/<owner>`` if ``url`` names a GitHub organization or user, else None.

    Accepts ``https://github.com/<owner>``, ``github.com/<owner>`` and
    ``https://github.com/orgs/<owner>``. Repository forms (``owner/name``, …) return None.
    """
    m = _GITHUB_OWNER.match(url.strip().rstrip("/"))
    return f"https://github.com/{m.group(1)}" if m else None


def _api_get(url: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "skill-atlas"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as resp:
            return json.load(resp)
    except HTTPError as e:
        try:
            message = json.load(e).get("message", "")
        except (ValueError, AttributeError):
            message = ""
        reason = f"HTTP {e.code}" + (f": {message}" if message else "")
        if e.code in (403, 429) and "rate limit" in message.lower():
            reason += " (set GITHUB_TOKEN to raise the limit)"
        raise RepoError(f"GitHub API: {reason}") from e
    except (URLError, OSError, ValueError) as e:
        raise RepoError(f"GitHub API: {getattr(e, 'reason', e)}") from e


def list_owner_repos(owner_url: str, *, include_forks: bool = False) -> tuple[list[str], int]:
    """Public repositories of a GitHub owner, as normalized URLs sorted by name, and the number of skipped forks.

    ``owner_url`` is a :func:`github_owner_url` result. Raises :class:`RepoError` if the owner
    doesn't exist or the API fails.
    """
    owner = owner_url.rsplit("/", 1)[1]
    api = os.environ.get("SKILL_ATLAS_GITHUB_API", "https://api.github.com").rstrip("/")
    entries: list[dict] = []
    page = 1
    while True:
        url = (
            f"{api}/users/{quote(owner)}/repos?type=owner&sort=full_name"
            f"&per_page={PER_PAGE}&page={page}"
        )
        try:
            batch = _api_get(url)
        except RepoError as e:
            if isinstance(e.__cause__, HTTPError) and e.__cause__.code == 404:
                raise RepoError(f"GitHub user or organization not found: {owner}") from e
            raise
        entries += batch
        if len(batch) < PER_PAGE:
            break
        page += 1
    forks = sum(1 for r in entries if r.get("fork"))
    if include_forks:
        forks = 0
    else:
        entries = [r for r in entries if not r.get("fork")]
    names = sorted({r["full_name"] for r in entries}, key=lambda n: (n.lower(), n))
    return [f"https://github.com/{name}" for name in names], forks


def github_slug(repo: str) -> str | None:
    """``owner/name`` for a normalized GitHub URL, else None."""
    m = _GITHUB_REPO.match(repo)
    return m.group(1) if m else None


def github_blob_url(repo: str, commit: str, path: str) -> str | None:
    """Link to ``path`` at ``commit`` on GitHub, or None if ``repo`` isn't a GitHub repository."""
    if not github_slug(repo):
        return None
    return f"{repo}/blob/{commit}/{quote(path, safe='/')}"


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *_NO_LFS, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as e:
        raise RepoError("git executable not found; please install git") from e
    except subprocess.CalledProcessError as e:
        raise RepoError(e.stderr.strip() or f"git {' '.join(args)} failed") from e
    return result.stdout.strip()


@contextmanager
def clone(url: str, ref: str | None = None) -> Iterator[tuple[Path, str]]:
    """Shallow-clone ``url`` into a temp dir; yield ``(path, commit_sha)``.

    The clone is blobless and sparse: only SKILL.md files under
    ``.agents/skills`` and ``.claude/skills`` are checked out, so even very large repositories are cheap to scan.
    """
    tmp = Path(tempfile.mkdtemp(prefix="skill-atlas-"))
    try:
        dest = tmp / "repo"
        args = ["clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "--quiet"]
        if ref:
            args += ["--branch", ref]
        _git(*args, url, str(dest))
        try:
            _git("rev-parse", "--verify", "--quiet", "HEAD", cwd=dest)
        except RepoError:
            raise EmptyRepoError("repository is empty") from None
        _git("sparse-checkout", "set", "--no-cone", *SPARSE_PATTERNS, cwd=dest)
        _git("checkout", "--quiet", cwd=dest)
        commit = _git("rev-parse", "HEAD", cwd=dest)
        yield dest, commit
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
