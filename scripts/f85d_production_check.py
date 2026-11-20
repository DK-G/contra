"""F-85-D production check (2026-11-20): join every bybridge materials result in the session logs
with the caller's delegate_finalize scores in the same session, and split by home Domain.

No API. Writes output/f91/f85d_runs.json and prints one row per run.
anomaly = purpose_sim < 0.20 (same as F-85-D's 1,680-candidate baseline).
"""
import datetime, glob, json, os, re, sys
sys.path.insert(0, "D:/dev/repos/contra")
from src.pipeline.query import OPENALEX_FIELDS
from src.pipeline.collect import FIELD_DOMAIN

NAME_DOMAIN = {name: FIELD_DOMAIN.get(fid) for fid, name in OPENALEX_FIELDS.items()}
NAME_TO_ID = {name: fid for fid, name in OPENALEX_FIELDS.items()}
ROW_FIELD = 7  # BRIDGE_SIGNAL_ROW_ORDER index of openalex_field


def short(i):
    return str(i).rsplit("/", 1)[-1]


def blocks(c):
    cc = c.get("content")
    if isinstance(cc, list):
        return "".join(x.get("text", "") for x in cc if isinstance(x, dict))
    return cc or ""


def materials(text, sess):
    m = re.search(r"saved to:?\s*(\S+\.txt)", text)
    if m and os.path.exists(m.group(1)):
        raw = open(m.group(1), encoding="utf-8", errors="replace").read()
        try:
            data = json.loads(raw)
            text = "".join(b.get("text", "") for b in data) if isinstance(data, list) else raw
        except json.JSONDecodeError:
            text = raw
    k = text.find("\n[\n{")
    if k < 0:
        return None, text
    end = text.rfind("\n]")
    try:
        return json.loads(text[k:end + 2]), text
    except json.JSONDecodeError:
        return None, text


def field_of(m):
    sig = m.get("bridge_signals")
    if isinstance(sig, dict):
        return sig.get("openalex_field")
    row = m.get("bridge_signals_row")
    if isinstance(row, list) and len(row) > ROW_FIELD:
        return row[ROW_FIELD]
    return None


runs = []
for path in sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))):
    if os.path.getmtime(path) < 1760000000:  # ~2025-10-09
        continue
    text = open(path, encoding="utf-8", errors="replace").read()
    if "bybridge_collect" not in text or "delegate_finalize" not in text:
        continue
    uses, results, finals = {}, [], []
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        for c in (rec.get("message") or {}).get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and "bybridge_collect" in c.get("name", ""):
                uses[c["id"]] = (rec.get("timestamp"), c["input"])
            elif c.get("type") == "tool_use" and "delegate_finalize" in c.get("name", ""):
                finals.append(c["input"])
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in uses:
                results.append((uses[c["tool_use_id"]], blocks(c)))
    for (ts, args), res in results:
        if not args.get("materials"):
            continue
        mats, full = materials(res, path)
        if not mats:
            continue
        ids = {short(m["id"]): field_of(m) for m in mats}
        best = None
        for f in finals:
            cands = f.get("candidates") or f.get("scored") or []
            sc = {short(c.get("id")): c.get("purpose_sim") for c in cands if isinstance(c, dict)}
            ov = len(set(sc) & set(ids))
            if ov >= max(5, len(ids) // 3):
                best = sc  # last overlapping call wins
        if not best:
            continue
        home = args.get("scope_field")
        home_dom = FIELD_DOMAIN.get(NAME_TO_ID.get(home, ""), None)
        on = "F-85-D" in full
        rows = []
        for i, fld in ids.items():
            ps = best.get(i)
            if not isinstance(ps, (int, float)):
                continue
            dom = NAME_DOMAIN.get(fld)
            rows.append({"id": i, "field": fld, "in_home_domain": (dom == home_dom) if dom and home_dom else None,
                         "ps": ps})
        runs.append({"ts": ts, "session": os.path.basename(path), "theme": (args.get("theme_overview") or "")[:70],
                     "home": home, "f85d_on": on, "rows": rows})

runs.sort(key=lambda r: r["ts"] or "")
json.dump(runs, open("D:/dev/repos/contra/output/f91/f85d_runs.json", "w", encoding="utf-8"), ensure_ascii=False)
for r in runs:
    rows = r["rows"]
    n = len(rows); a = sum(x["ps"] < 0.20 for x in rows); g = sum(x["ps"] >= 0.35 for x in rows)
    ind = [x for x in rows if x["in_home_domain"]]
    print(f"{(r.get('ts') or '?')[:16]} on={int(r['f85d_on'])} n={n:2d} anom={a:2d}({a/max(n,1):.0%}) ge35={g:2d} "
          f"inDom={len(ind):2d} inDomAnom={sum(x['ps']<0.20 for x in ind):2d} | {r['home']} | {r['theme'][:50]}")


# ---- summary (seihai's 07:00 loop runs only, OFF vs ON by weekday lane) ----
LANE = {0: "r01", 1: "r02", 2: "r03", 3: "r04", 4: "r05", 5: "weekly", 6: "sun"}
seen = set(); rows = []
for r in runs:
    ts = r.get("ts")
    if not ts or r["home"] != "Economics, Econometrics and Finance": continue
    t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) + datetime.timedelta(hours=9)
    if not (7 <= t.hour <= 8) or t.date() < datetime.date(2026, 10, 1): continue  # seihai's 07:05 loop
    if t.date() in seen: continue
    seen.add(t.date())
    xs = r["rows"]; n = len(xs)
    ind = [x for x in xs if x["in_home_domain"]]; out = [x for x in xs if x["in_home_domain"] is False]
    a = lambda L: sum(x["ps"] < 0.20 for x in L)
    rows.append(dict(d=str(t.date()), lane=LANE[t.weekday()], on=r["f85d_on"], n=n, an=a(xs),
                     ge=sum(x["ps"] >= 0.35 for x in xs), ni=len(ind), ai=a(ind), no=len(out), ao=a(out)))
for x in rows: print(x)
def agg(L):
    n=sum(x["n"] for x in L); 
    return dict(runs=len(L), n=n, anom=f'{sum(x["an"] for x in L)/n:.0%}', ge35=f'{sum(x["ge"] for x in L)/n:.0%}',
                inDom_share=f'{sum(x["ni"] for x in L)/n:.0%}',
                inDom_anom=f'{sum(x["ai"] for x in L)/max(1,sum(x["ni"] for x in L)):.0%}',
                outDom_anom=f'{sum(x["ao"] for x in L)/max(1,sum(x["no"] for x in L)):.0%}')
print("OFF all", agg([x for x in rows if not x["on"]]))
print("ON  all", agg([x for x in rows if x["on"]]))
for lane in ["r02","r03","r04","r05"]:
    off=[x for x in rows if not x["on"] and x["lane"]==lane]; on=[x for x in rows if x["on"] and x["lane"]==lane]
    print(lane, "OFF", [(x["d"][5:], x["an"], x["ni"]) for x in off], "| ON", [(x["d"][5:], x["an"], x["ni"]) for x in on])
