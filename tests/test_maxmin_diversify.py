"""Tests for MAX-MIN concept-Jaccard diversification (classify._maxmin_diversify).

Pre-scoring pool diversification: when the merged Track B pool exceeds the scoring cap,
pick the mutually most-distant subset (distance = 1 - concept Jaccard) so the P/M budget
covers diverse domains instead of truncating by arbitrary list order.
"""

from __future__ import annotations

from typing import List

from src.core.models import Concept, Work
from src.pipeline.classify import _maxmin_diversify


def _work(wid: str, concept_names: List[str]) -> Work:
    return Work(
        id=wid,
        title=wid,
        year=2020,
        venue="",
        doi=None,
        cited_by_count=0,
        abstract="abstract",
        concept_tags=[Concept(name=n, level=1, score=0.5, id=n) for n in concept_names],
    )


def test_returns_all_when_pool_not_larger_than_k():
    works = [_work("W0", ["A"]), _work("W1", ["B"])]
    out = _maxmin_diversify(works, 5)
    assert [w.id for w in out] == ["W0", "W1"]  # unchanged order, all kept


def test_k_zero_returns_empty():
    assert _maxmin_diversify([_work("W0", ["A"])], 0) == []


def test_picks_distant_over_near_duplicate():
    # W0 seed (A,B); two duplicates share both concepts; Wfar shares none.
    works = [
        _work("W0", ["A", "B"]),
        _work("Wdup1", ["A", "B"]),
        _work("Wfar", ["X", "Y"]),
        _work("Wdup2", ["A", "B"]),
    ]
    out = _maxmin_diversify(works, 2)
    ids = {w.id for w in out}
    assert ids == {"W0", "Wfar"}  # the far paper beats the duplicates for the 2nd slot


def test_orders_by_descending_min_distance():
    # len(works) > k so the MAX-MIN loop actually runs (k>=len short-circuits to input order).
    works = [
        _work("W0", ["A", "B"]),
        _work("Wdup1", ["A", "B"]),
        _work("Wfar", ["X", "Y"]),
        _work("Wdup2", ["A", "B"]),
    ]
    out = _maxmin_diversify(works, 3)
    # Seed W0, then the farthest (Wfar, min-dist 1.0), then a remaining duplicate (first by order).
    assert [w.id for w in out] == ["W0", "Wfar", "Wdup1"]


def test_deterministic_across_calls():
    works = [_work(f"W{i}", [f"C{i % 3}", f"D{i % 2}"]) for i in range(10)]
    a = [w.id for w in _maxmin_diversify(works, 5)]
    b = [w.id for w in _maxmin_diversify(works, 5)]
    assert a == b


def test_handles_works_without_concepts():
    # Works with no level>=1 concepts -> jaccard 0.0 with everything; must not crash.
    works = [
        _work("W0", []),
        _work("W1", []),
        _work("Wfar", ["X"]),
    ]
    out = _maxmin_diversify(works, 2)
    assert len(out) == 2
    assert out[0].id == "W0"  # seed is stable input order
