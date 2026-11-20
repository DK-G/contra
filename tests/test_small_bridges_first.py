"""F-85-S (2026-11-21): bybridge's opt-in bridge_order:"small_first" walks the pool from the
least-cited bridge, so a benchmark suite every seed evaluates on (llm-evolve 2026-11-20:
RESISC45 / CLIP / DTD / GTSRB ...) fills only the slots the method bridges could not."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.bridge_diagnostics import render_small_bridges_first, small_bridges_first

FULL = "https://openalex.org/{}"


def _pool(*ids):
    return [FULL.format(i) for i in ids]


# sizes from the llm-evolve 2026-11-20 pool (cited_by_count on 2026-11-21)
CITED = {"W4221155125": 1959, "W3214411122": 825, "W2592962403": 3760, "W3135367836": 61485, "W4306800001": 390}


def test_least_cited_first():
    pool = _pool("W4221155125", "W3214411122", "W2592962403", "W3135367836", "W4306800001")   # seed-share order
    assert small_bridges_first(pool, CITED) == _pool("W4306800001", "W3214411122", "W4221155125", "W2592962403", "W3135367836")


def test_ties_keep_pool_order_and_unknown_go_last():
    cited = {"W101": 100, "W102": 100, "W103": 50}
    pool = _pool("W102", "W199", "W101", "W103")          # W199: liveness failed open, size unknown
    assert small_bridges_first(pool, cited) == _pool("W103", "W102", "W101", "W199")


def test_lexical_only_tail_stays_at_the_end():
    # F-66 put the last two (lexical-only) at the end; small_first must not pull them forward
    pool = _pool("W3135367836", "W4221155125", "W4306800001", "W3214411122")
    out = small_bridges_first(pool, CITED, keep_tail=2)
    assert out == _pool("W4221155125", "W3135367836", "W4306800001", "W3214411122")


def test_diagnostic_line_names_the_switch_back():
    pool = small_bridges_first(_pool("W3135367836", "W4306800001", "W199"), CITED)
    line = render_small_bridges_first(pool, CITED, keep_tail=0)
    assert "F-85-S" in line and "390〜61,485" in line and "不明 1 本" in line
    assert 'bridge_order:"pool"' in line


def test_bybridge_schema_offers_the_opt_in_with_pool_default():
    from src.mcp_server import StdinMcpServer
    tools = StdinMcpServer().list_tools()
    schema = next(t for t in tools if t["name"] == "bybridge_collect")["inputSchema"]["properties"]
    assert schema["bridge_order"]["default"] == "pool"
    assert schema["bridge_order"]["enum"] == ["pool", "small_first"]
