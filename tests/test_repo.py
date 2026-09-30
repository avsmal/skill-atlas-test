import pytest

from skill_atlas.repo import normalize_repo_url


@pytest.mark.parametrize("url", [
    "https://github.com/JetBrains/kotlin",
    "https://github.com/JetBrains/kotlin/",
    "https://github.com/JetBrains/kotlin.git",
    "github.com/JetBrains/kotlin",
    "git@github.com:JetBrains/kotlin.git",
    "JetBrains/kotlin",
])
def test_normalize(url):
    assert normalize_repo_url(url) == "https://github.com/JetBrains/kotlin"


def test_github_blob_url():
    from skill_atlas.repo import github_blob_url

    sha = "a" * 40
    assert github_blob_url("https://github.com/o/r", sha, ".claude/skills/x y/SKILL.md") == (
        f"https://github.com/o/r/blob/{sha}/.claude/skills/x%20y/SKILL.md"
    )
    assert github_blob_url("file:///tmp/r", sha, "a/SKILL.md") is None
    assert github_blob_url("https://gitlab.com/o/r", sha, "a/SKILL.md") is None
