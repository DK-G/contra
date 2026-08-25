"""F-01 root cause — dangling reference ids must not be seated as bridges.

Measured on the seihai theme family (2026-08-25, docs/field_observations_seihai.md): the
bridge that 59 of 60 cross-domain candidates routed through was ``W4285719527``, an id that
OpenAlex does **not** resolve (404; zero hits by ``ids.openalex``) yet which sits in
**4,906,577** reference lists. ``referenced_works`` is a raw reference list, so ids of merged
or deleted records live on inside every citing paper — a bibliographic scar, not a shared
intellectual ancestor. Because the 2-hop scan ORs the whole pool into a single ``cites:``
filter, one such phantom swallows the entire result set.

The numbers below are the measured ones, not invented: the same pool held four further dead
ids at 4,194 / 2,749 / 554 / 59 citers while its largest LIVE bridges were Fama-French
(27,948) and GARCH (22,513). Size therefore does not separate phantoms from real ancestors —
resolvability does. These cases pin that, plus the fail-open behaviour that keeps a transient
OpenAlex failure from emptying the pool.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import Work
from src.pipeline.bridge_diagnostics import (
    filter_live_bridges,
    resolve_ids_batched,
    seed_rows,
)

FULL = "https://openalex.org/{}"


class FakeClient:
    """Returns only the ids it was told exist; records the calls it received."""

    def __init__(self, alive):
        self.alive = set(alive)
        self.calls = []

    def get(self, params):
        self.calls.append(params)
        asked = params["filter"].split(":", 1)[1].split("|")
        return {"results": [{"id": FULL.format(i)} for i in asked if i in self.alive]}


class BoomClient:
    def get(self, params):
        raise RuntimeError("openalex transport failure")


class EmptyClient:
    def get(self, params):
        return {"results": []}


def _pool(*short_ids):
    return [FULL.format(s) for s in short_ids]


def test_the_measured_phantom_is_dropped_and_the_live_classics_are_kept():
    # W4285719527 = the 4.9M-citer id that does not resolve; the rest are the pool's real
    # top bridges (Fama-French, GARCH, Fama 1970) which must survive untouched.
    pool = _pool("W4285719527", "W1995834279", "W2131773668", "W2104795328")
    client = FakeClient(["W1995834279", "W2131773668", "W2104795328"])
    live, dead = filter_live_bridges(pool, client)
    assert dead == ["W4285719527"]
    assert live == set(_pool("W1995834279", "W2131773668", "W2104795328"))


def test_all_five_measured_dead_ids_are_dropped_regardless_of_citer_count():
    # The five dead ids actually observed in one 50-strong pool. Their citer counts spanned
    # 4,906,577 down to 59 — a centrality/degree penalty would have caught at most the first.
    dead_ids = ["W4285719527", "W3122727604", "W6738184376", "W3122719819", "W3125066342"]
    pool = _pool(*dead_ids, "W1995834279")
    live, dead = filter_live_bridges(pool, FakeClient(["W1995834279"]))
    assert sorted(dead) == sorted(dead_ids)
    assert live == set(_pool("W1995834279"))


def test_ids_are_returned_in_the_callers_full_form():
    """Short ids would silently zero every bridge statistic downstream.

    Regression guard for the bug this fix introduced on its first run: bridges are compared
    against ``Work.referenced_works``, which holds full URLs, so the surviving pool must keep
    the caller's own string form. With short ids returned, all 20 seeds reported 'bridge 寄与
    0 本' and the concentration meter went blank.
    """
    pool = _pool("W1", "W2")
    live, _dead = filter_live_bridges(pool, FakeClient(["W1", "W2"]))
    assert live == {"https://openalex.org/W1", "https://openalex.org/W2"}
    seed = Work(
        id="S1", title="s", year=2020, venue="v", doi=None, cited_by_count=1,
        abstract="a", referenced_works=list(pool),
    )
    assert seed_rows([seed], live)[0].bridge_contribution == 2


def test_transport_failure_fails_open_and_drops_nothing():
    pool = _pool("W1", "W2")
    live, dead = filter_live_bridges(pool, BoomClient())
    assert dead == []
    assert live == set(pool)


def test_an_all_dead_answer_is_treated_as_a_bad_response_not_as_truth():
    """Emptying the pool would turn a hiccup into a silent zero harvest (the F-12 shape)."""
    pool = _pool("W1", "W2")
    live, dead = filter_live_bridges(pool, EmptyClient())
    assert dead == []
    assert live == set(pool)


def test_empty_input_is_not_an_api_call():
    client = FakeClient([])
    live, dead = filter_live_bridges([], client)
    assert (live, dead) == (set(), [])
    assert client.calls == []


def test_a_fifty_strong_pool_costs_exactly_one_call():
    pool = _pool(*[f"W{i}" for i in range(50)])
    client = FakeClient([f"W{i}" for i in range(50)])
    filter_live_bridges(pool, client)
    assert len(client.calls) == 1


def test_larger_pools_are_chunked_rather_than_truncated():
    """A silently truncated batch would mark the unchecked tail dead and delete it."""
    ids = [f"W{i}" for i in range(120)]
    client = FakeClient(ids)
    live = resolve_ids_batched([FULL.format(i) for i in ids], client, chunk=50)
    assert len(client.calls) == 3
    assert len(live) == 120


def test_duplicate_ids_are_asked_once_and_survive_once():
    pool = _pool("W1", "W1", "W2")
    client = FakeClient(["W1", "W2"])
    live, dead = filter_live_bridges(pool, client)
    assert dead == []
    assert live == set(_pool("W1", "W2"))
    assert client.calls[0]["filter"].count("|") == 1
