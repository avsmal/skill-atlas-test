import subprocess
from pathlib import Path

import pytest


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def write_skill(root: Path, rel_dir: str, frontmatter: str, body: str = "Body\n") -> None:
    d = root / rel_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


@pytest.fixture
def fixture_repo(tmp_path) -> Path:
    """A local git repo with two valid skills and one malformed one."""
    root = tmp_path / "src-repo"
    root.mkdir()
    write_skill(root, ".claude/skills/pdf", "name: pdf\ndescription: Work with PDF files")
    write_skill(root, "plugins/x/skills/review", "description: >\n  Review code\n  carefully")
    (root / "broken").mkdir()
    (root / "broken" / "SKILL.md").write_text("no frontmatter here\n")
    (root / "README.md").write_text("hi\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return root
