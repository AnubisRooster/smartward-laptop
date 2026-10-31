"""Instant search for the command palette, and the things worth a desktop notification."""
import threading
from . import db

_lock = threading.Lock()
_seen = {"articles": None, "sources": {}, "approvals": set(), "memo": None, "watch": None}   # None: nothing baselined yet since the app started


def _like(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def quick_search(q, limit=6):
    """Matches by name, per kind. Plain substring match so it is instant and needs no model."""
    q = (q or "").strip()
    if not q: return {"articles": [], "themes": [], "projects": [], "conversations": [], "sources": []}
    p = _like(q)
    s = lambda sql, *a: db.q(sql, (p,) * len(a) + (limit,))
    return {
        "articles": s("SELECT id,title FROM articles WHERE title LIKE ? ESCAPE '\\' AND source_id IN (SELECT id FROM sources) ORDER BY published DESC LIMIT ?", 1),
        "themes": s("SELECT id,name,type FROM themes WHERE name LIKE ? ESCAPE '\\' OR aliases LIKE ? ESCAPE '\\' ORDER BY name LIMIT ?", 1, 2),
        "projects": s("SELECT id,name FROM projects WHERE name LIKE ? ESCAPE '\\' ORDER BY updated DESC LIMIT ?", 1),
        "conversations": s("SELECT id,title FROM conversations WHERE title LIKE ? ESCAPE '\\' ORDER BY updated DESC LIMIT ?", 1),
        "sources": s("SELECT id,name FROM sources WHERE name LIKE ? ESCAPE '\\' ORDER BY name LIMIT ?", 1),
    }


def poll():
    """What is new since the last poll. Each thing is reported once; the first poll after the app starts reports nothing
    for things that already existed (otherwise every launch would announce the whole library)."""
    want = lambda k: bool(db.get_setting(k))
    out = []
    with _lock:
        fresh = db.q("SELECT id,title,relevance FROM articles WHERE relevant=1 AND relevance IS NOT NULL AND read=0 AND source_id IN (SELECT id FROM sources)")
        ids = {a["id"] for a in fresh}
        if _seen["articles"] is None: _seen["articles"] = ids
        else:
            new = [a for a in fresh if a["id"] not in _seen["articles"]]
            _seen["articles"] |= ids
            if new and want("notify_articles"):
                top = max(new, key=lambda a: a["relevance"])
                out.append({"kind": "articles", "title": f"{len(new)} new article{'s' if len(new) != 1 else ''} for you", "body": top["title"], "count": len(new)})
        for s in db.q("SELECT id,name,last_status,last_fetched,last_error FROM sources WHERE enabled=1"):
            if s["last_status"] != "error": _seen["sources"].pop(s["id"], None); continue
            if s["id"] not in _seen["sources"]:
                _seen["sources"][s["id"]] = True
                if want("notify_sources"): out.append({"kind": "source", "title": f"“{s['name']}” couldn’t be refreshed", "body": (s["last_error"] or "")[:140]})
        pend = db.q("SELECT id,title FROM approvals WHERE status='pending'")
        new = [a for a in pend if a["id"] not in _seen["approvals"]]
        _seen["approvals"] = {a["id"] for a in pend}
        if new and want("notify_approvals"): out.append({"kind": "approval", "title": "Waiting for your approval", "body": new[0]["title"]})
        m = db.q("SELECT id,week FROM memos ORDER BY created DESC LIMIT 1", one=True)
        mid = m["id"] if m else 0
        if _seen["memo"] is not None and mid != _seen["memo"] and m and want("notify_memo"): out.append({"kind": "memo", "title": "This week’s memo is ready", "body": f"Week {m['week']}: open the Radar to read it."})
        _seen["memo"] = mid
        top = (db.q("SELECT MAX(id) n FROM watch_hits", one=True) or {}).get("n") or 0
        if _seen["watch"] is not None and top > _seen["watch"]:
            n = db.q("SELECT COUNT(*) n FROM watch_hits WHERE id>? AND notified!=2", (_seen["watch"],), one=True)["n"]
            if n and want("notify_watches"): out.append({"kind": "watch", "title": f"{n} new watch match{'es' if n != 1 else ''}", "body": "Open the Radar to see them."})
        _seen["watch"] = top
    if db.get_setting("lock_enabled"):          # a locked app shouldn't show titles on the desktop
        for e in out: e["body"] = "Open SmartWard to see details."
    return out


def reset():
    with _lock: _seen.update({"articles": None, "sources": {}, "approvals": set(), "memo": None, "watch": None})
