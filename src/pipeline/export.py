"""Export utilities (Phase 1 stub)."""

from __future__ import annotations

from pathlib import Path

from src.core.models import OutputDocument
from src.core.output_spec import render_markdown


def export_markdown(doc: OutputDocument, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(doc), encoding="utf-8")


__all__ = ["export_markdown"]
