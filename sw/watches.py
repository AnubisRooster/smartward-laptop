"""Watches: saved rules like "SGLang or vLLM, speculative decoding, measured results only", checked against every new article and development.

No model is used: a watch matches by whole words (the same rule as domains), optionally limited to domains, sources and how strong the evidence is.
A hit is recorded once per article. A new watch looks back two weeks so it isn't empty, but those first hits are never announced."""
import json
from . import db, signals

EVIDENCE = ("any", "claimed", "measured")          # "claimed" means claimed or measured
RANK = {"anecdotal": 0, "claimed": 1, "measured": 2}
BACKFILL_DAYS = 14


def _clean(body, partial=False):
    out = {}
    if not partial or "name" in body: out["name"] = str(body.get("name") or "").strip()[:80]
    for k in ("terms", "domains"):
        if not partial or k in body:
            v = body.get(k) or []
            if isinstance(v, str): v = v.split(",")
            out[k] = [str(x).strip()[:60] for x in v if str(x).strip()][:12]
    if not partial or "sources" in body: out["sources"] = [int(x) for x in (body.get("sources") or []) if str(x).isdigit()][:20]
    if not partial or "min_evidence" in body:
        out["min_evidence"] = body.get("min_evidence") or "any"
        if out["min_evidence"] not in EVIDENCE: raise ValueError("Evidence must be any, claimed or measured.")
    if "enabled" in body: out["enabled"] = 1 if body["enabled"] else 0
    if not partial:
        if not out["terms"] and not out["domains"]: raise ValueError("A watch needs some words or a domain.")
        out["name"] = out["name"] or ", ".join(out["terms"] or out["domains"])[:80]
    elif "name" in out and not out["name"]: raise ValueError("Give the watch a name.")
    return out


def create(body, now=None):
    w = _clean(body); now = now or db.now()
    wid = db.x("INSERT INTO watches(name,terms,domains,sources,min_evidence,enabled,scanned,created) VALUES(?,?,?,?,?,1,?,?)",
               (w["name"], json.dumps(w["terms"]), json.dumps(w["domains"]), json.dumps(w["sources"]), w["min_evidence"], now - BACKFILL_DAYS * 86400, now))
    scan(now, only=wid, announce=False)
    return get(wid)


def update(wid, body):
    if not db.q("SELECT 1 FROM watches WHERE id=?", (wid,), one=True): raise LookupError("No such watch.")
    w = _clean(body, partial=True)
    for k, v in w.items(): db.x(f"UPDATE watches SET {k}=? WHERE id=?", (json.dumps(v) if isinstance(v, list) else v, wid))
    return get(wid)


def delete(wid):
    db.x("DELETE FROM watch_hits WHERE watch_id=?", (wid,)); db.x("DELETE FROM watches WHERE id=?", (wid,))


def _row(w):
    for k in ("terms", "domains", "sources"): w[k] = json.loads(w[k] or "[]")
    return w


def get(wid):
    w = db.q("SELECT * FROM watches WHERE id=?", (wid,), one=True)
    return _row(w) if w else None


def listing(hits=5):
    out = []
    for w in db.q("SELECT * FROM watches ORDER BY created DESC"):
        w = _row(w)
        w["count"] = db.q("SELECT COUNT(*) n FROM watch_hits WHERE watch_id=?", (w["id"],), one=True)["n"]
        w["hits"] = db.q("SELECT h.article_id,h.dev_id,h.ts,a.title,s.name source,d.claim,d.evidence FROM watch_hits h JOIN articles a ON a.id=h.article_id JOIN sources s ON s.id=a.source_id "
                         "LEFT JOIN developments d ON d.id=h.dev_id WHERE h.watch_id=? ORDER BY h.ts DESC LIMIT ?", (w["id"], hits))
        out.append(w)
    return out


def _matcher(w, domains):
    """(words_ok, in_domain_text, domain names): words_ok and in_domain_text test a piece of text."""
    words = signals.keyword_regex(w["terms"]) if w["terms"] else None
    dom = [d for d in domains if d["name"] in w["domains"]]
    dom_rx = signals.keyword_regex([k for d in dom for k in d["keywords"]]) if dom else None
    return (lambda t: words is None or bool(words.search(t.lower()))), (lambda t: dom_rx is None or bool(dom_rx.search(t.lower()))), {d["name"] for d in dom}


def scan(now=None, only=None, announce=True):
    """Check new articles and developments against the watches. Returns how many new hits there are to announce."""
    now = now or db.now(); domains = signals.domains(); fresh = 0
    for w in db.q("SELECT * FROM watches WHERE enabled=1" + (" AND id=?" if only else ""), (only,) if only else ()):
        w = _row(w); since = w["scanned"] or w["created"]; words_ok, in_domain_text, dom_names = _matcher(w, domains)
        src = set(w["sources"]); found = {}
        devs = db.q("SELECT d.id,d.article_id,d.subject,d.claim,d.evidence,d.domains,a.source_id,a.title FROM developments d JOIN articles a ON a.id=d.article_id "
                    "WHERE d.grounded=1 AND a.private=0 AND d.created>? AND d.created<=?", (since, now))
        for d in devs:
            if src and d["source_id"] not in src: continue
            if w["min_evidence"] != "any" and RANK.get(d["evidence"], 0) < RANK[w["min_evidence"]]: continue
            if (not dom_names or dom_names & set(json.loads(d["domains"] or "[]"))) and words_ok(f"{d['title']} {d['subject']} {d['claim']}"): found.setdefault(d["article_id"], d["id"])
        if w["min_evidence"] == "any":
            arts = db.q("SELECT id,source_id,title,teaser,text FROM articles WHERE relevant=1 AND private=0 AND created>? AND created<=?", (since, now))
            for a in arts:
                if a["id"] in found or (src and a["source_id"] not in src): continue
                t = f"{a['title']} {a['teaser'] or ''} {a['text'] or ''}"
                if words_ok(t) and in_domain_text(t): found[a["id"]] = None
        new = 0
        for aid, did in found.items():
            cur = db.q("SELECT id,dev_id FROM watch_hits WHERE watch_id=? AND article_id=?", (w["id"], aid), one=True)
            if cur:
                if did and not cur["dev_id"]: db.x("UPDATE watch_hits SET dev_id=? WHERE id=?", (did, cur["id"]))
                continue
            db.x("INSERT INTO watch_hits(watch_id,article_id,dev_id,ts,notified) VALUES(?,?,?,?,?)", (w["id"], aid, did, now, 0 if announce else 2)); new += 1     # 2: a look-back hit, never announced
        db.x("UPDATE watches SET scanned=?" + (", last_hit=?" if new else "") + " WHERE id=?", (now, now, w["id"]) if new else (now, w["id"]))
        if announce: fresh += new
    return fresh


def unannounced():
    """Hits not yet announced, as (count, number of watches); marks them announced."""
    rows = db.q("SELECT id,watch_id FROM watch_hits WHERE notified=0")
    if rows: db.x(f"UPDATE watch_hits SET notified=1 WHERE id IN ({','.join('?' * len(rows))})", [r["id"] for r in rows])
    return len(rows), len({r["watch_id"] for r in rows})
