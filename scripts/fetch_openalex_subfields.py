# -*- coding: utf-8 -*-
"""Cache the OpenAlex Subfield taxonomy into ``data/openalex_subfields.json``.

The F-13 seed-roster instrument resolves a theme's ``scope.field`` against Subfield NAMES,
and those names normally come from the metadata a run already fetched
(``src.pipeline.query.subfield_vocabulary``) — no API call, nothing to keep in sync. This
script is the optional enrichment: with the cache present, a scope can resolve even to a
Subfield that happens to appear nowhere in that run's roster, so a totally drifted roster
reads as "0% of the declared subject" instead of "判定不能".

    python scripts/fetch_openalex_subfields.py

Written as ``[[id, display_name, field_id], ...]``. The file is optional: every consumer
falls back to run metadata when it is missing (``load_subfield_taxonomy`` returns ``{}``).

Note (F-11): OpenAlex answers the anonymous pool with sustained HTTP 429 after a burst — on
2026-09-04 this script could not complete for that reason, which is exactly why the
instrument does not depend on it.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API = "https://api.openalex.org/subfields?per-page=200&page={page}&select=id,display_name,field"
OUT = Path(__file__).resolve().parents[1] / "data" / "openalex_subfields.json"


def fetch(url: str, attempts: int = 5) -> dict:
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "contra-cli/0.1"})
            with urllib.request.urlopen(req, timeout=45) as res:
                return json.load(res)
        except Exception as exc:  # noqa: BLE001 - retried, then reported verbatim
            last = exc
            print(f"[info] retry {i}: {exc}", flush=True)
            time.sleep(20 * (i + 1))
    raise SystemExit(f"could not reach OpenAlex: {last}")


def main() -> int:
    rows = []
    for page in (1, 2):
        payload = fetch(API.format(page=page))
        for r in payload.get("results", []):
            rows.append([
                str(r["id"]).rsplit("/", 1)[-1],
                str(r["display_name"]),
                str(r["field"]["id"]).rsplit("/", 1)[-1],
            ])
        print(f"[info] page {page}: {len(payload.get('results', []))} rows", flush=True)
        time.sleep(2)
    if len(rows) < 240:  # the taxonomy has ~252 subfields; a short read means a partial page
        raise SystemExit(f"refusing to write a partial cache ({len(rows)} rows)")
    rows.sort(key=lambda r: int(r[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] wrote {OUT} ({len(rows)} subfields)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
