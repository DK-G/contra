"""R3: verify _parse_pm_items maps the discrete purpose_level anchor to purpose_sim,
with backward-compatible float fallback. Fixture-free; run via the direct runner:

  python -c "import tests.test_purpose_level as t; [getattr(t,n)() for n in dir(t) if n.startswith('test_')]"
"""

from src.pipeline.classify import _parse_pm_items, _PURPOSE_LEVELS


def _item(**over):
    base = {
        "id": "W1",
        "mechanism_dist": 0.8,
        "connection_label": "Aが Bを律速する",
        "serendipity_rationale": "論文の〈X〉はテーマの〈Y〉に相当する",
    }
    base.update(over)
    return base


def _ps(item):
    rows = _parse_pm_items([item])
    assert len(rows) == 1, f"expected 1 parsed row, got {len(rows)}"
    return rows[0][1]["purpose_sim"]


def test_level_strong_maps_to_anchor():
    assert _ps(_item(purpose_level="strong")) == _PURPOSE_LEVELS["strong"] == 0.70


def test_level_partial_maps_to_anchor():
    assert _ps(_item(purpose_level="partial")) == _PURPOSE_LEVELS["partial"] == 0.45


def test_level_none_maps_to_anchor():
    assert _ps(_item(purpose_level="none")) == _PURPOSE_LEVELS["none"] == 0.10


def test_level_is_case_and_space_insensitive():
    assert _ps(_item(purpose_level="  Strong ")) == 0.70


def test_float_fallback_when_no_level():
    assert _ps(_item(purpose_sim=0.8)) == 0.8


def test_invalid_level_falls_back_to_float():
    # bogus label -> ignore, use the raw float that older payloads might still carry
    assert _ps(_item(purpose_level="bogus", purpose_sim=0.6)) == 0.6


def test_no_score_defaults_to_zero_but_row_survives():
    # neither field present -> purpose_sim 0.0 (anomaly-floored downstream), row still parsed
    assert _ps(_item()) == 0.0


def test_level_takes_precedence_over_float():
    # if both present, the discrete level wins (it is the calibrated signal)
    assert _ps(_item(purpose_level="none", purpose_sim=0.9)) == 0.10
