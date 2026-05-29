"""Theme-based history management for paper deduplication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Set

from src.core.models import ThemeHistory

_HISTORY_DIR = Path("data/history")


def compute_theme_hash(theme_overview: str) -> str:
    return hashlib.sha256(theme_overview.encode("utf-8")).hexdigest()[:16]


def load_history(theme_hash: str, history_dir: Path = _HISTORY_DIR) -> ThemeHistory:
    path = history_dir / f"{theme_hash}.json"
    if not path.exists():
        return ThemeHistory(theme_hash=theme_hash, used_ids=[], generated_at="")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ThemeHistory(theme_hash=theme_hash, used_ids=[], generated_at="")
    return ThemeHistory(
        theme_hash=data.get("theme_hash", theme_hash),
        used_ids=data.get("used_ids", []),
        generated_at=data.get("generated_at", ""),
    )


def save_history(
    history: ThemeHistory,
    new_ids: list,
    history_dir: Path = _HISTORY_DIR,
) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{history.theme_hash}.json"
    existing = load_history(history.theme_hash, history_dir)
    merged_ids = list(dict.fromkeys(existing.used_ids + new_ids))
    updated = ThemeHistory(
        theme_hash=history.theme_hash,
        used_ids=merged_ids,
        generated_at=datetime.now().isoformat(),
    )
    path.write_text(
        json.dumps(asdict(updated), ensure_ascii=False, indent=2), encoding="utf-8"
    )


__all__ = ["compute_theme_hash", "load_history", "save_history"]
