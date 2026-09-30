from skill_atlas.models import Skill
from skill_atlas.similarity import find_similar, similarity


def _s(repo, name, description, path=None, content=""):
    return Skill(repo, name, description, "c", path or f"{repo}/{name}/SKILL.md", content=content)


def test_identical_description_and_content_is_fully_similar():
    a = _s("r1", "a", "Work with PDF files", content="Convert PDFs to text.")
    b = _s("r2", "b", "Work with PDF files", content="Convert PDFs to text.")
    assert similarity(a, b) == 1.0


def test_completely_different_is_not_similar():
    a = _s("r1", "a", "Work with PDF files", content="Convert PDFs to text.")
    b = _s("r2", "b", "Deploy a Kubernetes cluster", content="Run kubectl apply on the manifests.")
    assert similarity(a, b) < 0.4


def test_description_and_content_are_averaged():
    # same description (ratio 1.0), unrelated content (ratio ~0.0) -> similarity near 0.5
    a = _s("r1", "a", "Work with PDF files", content="abc")
    b = _s("r2", "b", "Work with PDF files", content="xyz")
    assert 0.4 < similarity(a, b) < 0.6


def test_find_similar_excludes_self():
    target = _s("r1", "pdf", "Work with PDF files")
    same = Skill("r1", "pdf", "Work with PDF files", "c", target.path)
    other = _s("r2", "pdf2", "Work with PDF files")
    results = find_similar(target, [target, same, other])
    assert [c.repo for c, _ in results] == ["r2"]


def test_find_similar_excludes_at_or_below_threshold():
    target = _s("r1", "a", "Work with PDF files")
    identical = _s("r2", "b", "Work with PDF files")  # similarity == 1.0
    assert find_similar(target, [identical], threshold=1.0) == []
    assert find_similar(target, [identical], threshold=0.99) == [(identical, 1.0)]


def test_find_similar_sorted_descending():
    target = _s("r1", "a", "Work with PDF files", content="Convert PDFs to text and back.")
    close = _s("r2", "b", "Work with PDF files", content="Convert PDFs to text.")
    far = _s("r3", "c", "Work with PDF files", content="Something unrelated entirely.")
    results = find_similar(target, [far, close])
    assert [c.repo for c, _ in results] == ["r2", "r3"]
    assert results[0][1] > results[1][1]


def test_find_similar_ties_break_by_repo_then_name():
    target = _s("r1", "a", "Work with PDF files")
    x = _s("r3", "x", "Work with PDF files")
    y = _s("r2", "y", "Work with PDF files")
    results = find_similar(target, [x, y])
    assert [c.repo for c, _ in results] == ["r2", "r3"]


def test_threshold_is_exclusive():
    a = _s("r1", "a", "same text")
    b = _s("r2", "b", "same text")
    ratio = similarity(a, b)
    assert find_similar(a, [b], threshold=ratio) == []
    assert find_similar(a, [b], threshold=ratio - 0.001) == [(b, ratio)]
