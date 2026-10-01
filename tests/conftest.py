import os
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from skill_atlas.web import make_server


def _git(cwd, *args):
    # autocrlf off: keep CRLF fixtures byte-exact regardless of the user's global git config
    subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=cwd, check=True, capture_output=True)


def skill_md(name: str | None = None, description: str = "", body: str = "Body\n") -> str:
    fm = (f"name: {name}\n" if name else "") + (f"description: {description}\n" if description else "")
    return f"---\n{fm}---\n{body}"


def make_repo(
    root: Path,
    files: dict[str, str | bytes],
    symlinks: dict[str, str] | None = None,
) -> Path:
    """Create and commit a git repo at ``root`` with ``files`` and ``symlinks`` (path -> target)."""
    root.mkdir(parents=True)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
    for rel, target in (symlinks or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, p)
    if not files and not symlinks:
        (root / "README.md").write_text("empty\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return root


@pytest.fixture
def fixture_repo(tmp_path) -> Path:
    """Two valid skills, one malformed one, and one SKILL.md outside the workflow dirs."""
    return make_repo(tmp_path / "src-repo", {
        ".claude/skills/pdf/SKILL.md": skill_md("pdf", "Work with PDF files"),
        ".agents/skills/review/SKILL.md": "---\ndescription: >\n  Review code\n  carefully\n---\n",
        ".claude/skills/broken/SKILL.md": "no frontmatter here\n",
        "skills/product/SKILL.md": skill_md("product", "Shipped content"),
        "README.md": "hi\n",
    })


@pytest.fixture
def serve(tmp_path):
    """Start a server; returns ``get(path) -> (status, body)``, with the server's URL as ``get.base``."""
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
        get.base = base
        return get

    yield start
    for s in servers:
        s.shutdown()
        s.server_close()
