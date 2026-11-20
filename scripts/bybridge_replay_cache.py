"""Replay one real bybridge call against live OpenAlex once, caching every response (and every
pool bridge's citer page), so variants of the 2-hop scan can be compared on the SAME pages.
Written for F-85-S (llm-evolve 2026-11-20).

<work_dir> must hold bybridge_collect_args.json (the call's arguments, taken from the session
transcript). Outputs go to <work_dir>: oa_cache.pkl, capture.pkl, replay_<tag>.txt.

usage:
  python scripts/bybridge_replay_cache.py <contra_repo> <work_dir> record
  python scripts/bybridge_replay_cache.py <contra_repo> <work_dir> variants \
      '{"now":{}, "small":{"bridge_order":"small_first"}}'
"""
import json
import pickle
import sys
from pathlib import Path

repo, scratch, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(repo))

from src.openalex import client as oa_client  # noqa: E402

CACHE = scratch / "oa_cache.pkl"
cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
_orig_get = oa_client.OpenAlexClient.get


def _key(params):
    return json.dumps(params, sort_keys=True, default=str)


def cached_get(self, params):
    k = _key(params)
    if k in cache:
        return cache[k]
    if mode != "record":
        # variants must not fetch: a per_page difference re-asks the same filter -> take a
        # larger cached page with the same filter and cut it.
        f = str(params.get("filter", ""))
        if f.startswith("ids.openalex:"):
            want = set(f.split(":", 1)[1].split("|"))
            got = {"results": []}
            for kk, v in cache.items():
                p = json.loads(kk)
                pf = str(p.get("filter", ""))
                if pf.startswith("ids.openalex:") and p.get("select") == params.get("select"):
                    got["results"] += [r for r in v.get("results", [])
                                       if r.get("id", "").split("/")[-1] in want]
            if got["results"]:
                return got
        for kk, v in cache.items():
            p = json.loads(kk)
            if p.get("filter") == params.get("filter") and p.get("page", 1) == params.get("page", 1) \
                    and int(p.get("per_page", 0)) >= int(params.get("per_page", 0)):
                out = dict(v)
                out["results"] = list(v.get("results", []))[: int(params.get("per_page", 25))]
                return out
        raise RuntimeError(f"cache miss: {k[:300]}")
    v = _orig_get(self, params)
    cache[k] = v
    return v


oa_client.OpenAlexClient.get = cached_get

import src.mcp_server as ms  # noqa: E402
from src.mcp_server import StdinMcpServer  # noqa: E402
from src.pipeline import collect as col  # noqa: E402

CAPTURE = {}
_orig_ccc = ms.collect_citation_candidates


def capturing_ccc(seeds, config=None, **kw):
    CAPTURE["seeds"], CAPTURE["config"], CAPTURE["kw"] = seeds, config, kw
    return _orig_ccc(seeds, config, **kw)


ms.collect_citation_candidates = capturing_ccc

args = json.loads((scratch / "bybridge_collect_args.json").read_text(encoding="utf-8"))
args.pop("history_key", None)          # same pages regardless of what history now holds
args["use_history"] = False


def run(extra, tag):
    a = dict(args)
    a.update(extra)
    res = StdinMcpServer().handle_tool_call("bybridge_collect", a)
    text = "\n".join(b.get("text", "") for b in res.get("content", []))
    (scratch / f"replay_{tag}.txt").write_text(text, encoding="utf-8")
    return text


if mode == "record":
    # ask with the larger page (F-85-D ON = 24/bridge) so OFF (12) can be cut from it
    run({}, "on")
    seeds, kw = CAPTURE["seeds"], CAPTURE["kw"]
    home_field_ids = col.dominant_field_ids(seeds)
    home_topic_ids = col.dominant_topic_ids(seeds)
    c = col.Collector(col.CollectConfig())
    for b in kw["bridges"]:
        sq = col._citation_query([b], seeds, home_field_ids, 100, home_topic_ids)
        try:
            c.client.get(sq.to_params(per_page=24, page=1))
        except Exception as e:
            print("fail", b, e)
    pickle.dump({"seeds": seeds, "kw": kw}, open(scratch / "capture.pkl", "wb"))
    CACHE.write_bytes(pickle.dumps(cache))
    print("recorded", len(cache), "responses")
else:
    for tag, extra in json.loads(sys.argv[4]).items():
        run(extra, tag)
        print("ran", tag)
