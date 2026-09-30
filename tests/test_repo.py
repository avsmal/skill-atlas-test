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
