"""Skill-to-skill similarity, based on description and content. See spec/web.md."""
from __future__ import annotations

from difflib import SequenceMatcher

from .models import Skill

DEFAULT_THRESHOLD = 0.10


def similarity(a: Skill, b: Skill) -> float:
    """Similarity ratio in ``[0, 1]``: the average of the description and content ratios.

    Averaging (rather than concatenating the two texts) keeps a skill's often much longer
    ``content`` from drowning out its ``description`` in the score.
    """
    desc = SequenceMatcher(None, a.description, b.description).ratio()
    content = SequenceMatcher(None, a.content, b.content).ratio()
    return (desc + content) / 2


def find_similar(
    target: Skill, candidates: list[Skill], *, threshold: float = DEFAULT_THRESHOLD,
) -> list[tuple[Skill, float]]:
    """Skills from ``candidates`` more similar than ``threshold`` to ``target``.

    Excludes ``target`` itself (matched by ``repo`` + ``path``). Sorted by descending
    similarity, then by repo and name for a stable order among ties.
    """
    scored = (
        (c, similarity(target, c))
        for c in candidates
        if c.repo != target.repo or c.path != target.path
    )
    above = [(c, ratio) for c, ratio in scored if ratio > threshold]
    above.sort(key=lambda cr: (-cr[1], cr[0].repo, cr[0].name))
    return above
