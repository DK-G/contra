"""M3 saturation safety-net tests (fixture-free, no network).

Covers the deterministic pieces of the saturation path:
  - select_track_b populates `diag` and respects the empty-candidate early exit
  - _write_saturation_report emits an honest "saturated" note (no weak fallback padding)

Run with the direct runner (pytest/monkeypatch not available in this env):
  python -c "import tests.test_m3_saturation as t; [getattr(t,n)() for n in dir(t) if n.startswith('test_')]"
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.core.input_schema import validate_and_normalize
from src.pipeline.classify import select_track_b

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _theme():
    payload = json.loads((_REPO_ROOT / "data" / "samples" / "theme_social.json").read_text(encoding="utf-8"))
    return validate_and_normalize(payload)


def test_empty_pool_sets_diag():
    """No candidates -> [] and diag status 'empty_pool' (no LLM call)."""
    diag: dict = {}
    out = select_track_b([], _theme(), diag=diag)
    assert out == [], out
    assert diag.get("status") == "empty_pool", diag
    assert diag.get("qualified") == 0, diag


def test_emit_fallback_default_preserves_signature():
    """The new emit_fallback/diag params default-preserve old behaviour (empty in -> empty out)."""
    out = select_track_b([], _theme())  # no diag passed -> must not raise
    assert out == []


def test_saturation_report_written():
    """_write_saturation_report writes an honest 0-unit note, not a padded report."""
    from src.cli.main import _write_saturation_report

    class _Args:
        output_floor = 0.35

    diag = {"status": "saturated", "reason": "no_qualified",
            "scored": 12, "anomaly": 3, "hollow": 2, "passed": 1, "qualified": 0}
    with tempfile.TemporaryDirectory() as d:
        out_dir = Path(d)
        rc = _write_saturation_report(out_dir, _theme(), [1, 2, 3], diag, _Args())
        assert rc == 0
        md = (out_dir / "brainstorm_output.md").read_text(encoding="utf-8")
        assert "テーマ飽和" in md, md
        assert "接続点 0 件" in md, md
        assert "output_floor" in md, md  # reason label surfaced
        # must NOT have adopted/padded anything
        assert "qualified=0" in md, md


if __name__ == "__main__":
    for _n in [n for n in dir() if n.startswith("test_")]:
        globals()[_n]()
        print(f"PASS {_n}")
