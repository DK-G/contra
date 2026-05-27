from __future__ import annotations

from pathlib import Path
import sys


def remove_markers(text: str) -> str:
    lines = text.splitlines()
    filtered = [
        line
        for line in lines
        if "AUTO_SECTION" not in line
    ]
    return "\n".join(filtered) + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/remove_markers.py <markdown_path>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[error] file not found: {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    path.write_text(remove_markers(text), encoding="utf-8")
    print(f"[ok] removed markers: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
