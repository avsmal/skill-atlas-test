"""Repository URL handling and shallow cloning."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

_GITHUB_REPO = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+$")
_SHORTHAND = re.compile(r"^[\w.-]+/[\w.-]+$")
# gitignore-style patterns (non-cone sparse checkout) for rule (a) in spec/cli.md:
# <prefix>/.agents|.claude/skills/<skill-dir>/SKILL.md, file name in any case.
_SKILL_FILE_GLOB = "[Ss][Kk][Ii][Ll][Ll].[Mm][Dd]"
SPARSE_PATTERNS = [f"**/{d}/skills/*/{_SKILL_FILE_GLOB}" for d in (".agents", ".claude")]
# Never run Git LFS filters: skill files are plain text and git-lfs may be absent.
_NO_LFS = ["-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=", "-c", "filter.lfs.required=false"]


class RepoError(Exception):
    pass


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


def github_blob_url(repo: str, commit: str, path: str) -> str | None:
    """Link to ``path`` at ``commit`` on GitHub, or None if ``repo`` isn't a GitHub repository."""
    if not _GITHUB_REPO.match(repo):
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
        _git("sparse-checkout", "set", "--no-cone", *SPARSE_PATTERNS, cwd=dest)
        _git("checkout", "--quiet", cwd=dest)
        commit = _git("rev-parse", "HEAD", cwd=dest)
        yield dest, commit
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
