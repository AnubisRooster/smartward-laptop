"""Projects: brief with line-diff suggestions + history, items, links (URLs / GitHub repos, read-only)."""
import difflib, json, re
import httpx
from . import db, llm, sources

def diff_lines(old, new):
    out = []
    for l in difflib.ndiff((old or "").splitlines(), (new or "").splitlines()):
        if l.startswith("? "): continue
        out.append({"op": {"+": "add", "-": "del", " ": "same"}[l[0]], "text": l[2:]})
    return out

def get(pid):
    p = db.q("SELECT * FROM projects WHERE id=?", (pid,), one=True)
    if not p: return None
    p["items"] = db.q("SELECT * FROM items WHERE project_id=? ORDER BY done, ts DESC", (pid,))
    p["links"] = db.q("SELECT * FROM project_links WHERE project_id=?", (pid,))
    p["history"] = db.q("SELECT id,note,ts FROM brief_history WHERE project_id=? ORDER BY ts DESC", (pid,))
    p["suggestion"] = ({"reason": p["pending_reason"], "diff": diff_lines(p["brief"], p["pending_brief"]),
                        "added": sum(1 for d in diff_lines(p["brief"], p["pending_brief"]) if d["op"] == "add"),
                        "removed": sum(1 for d in diff_lines(p["brief"], p["pending_brief"]) if d["op"] == "del")} if p["pending_brief"] else None)
    return p

def update_brief(pid, brief, note="You edited the brief"):
    old = db.q("SELECT brief FROM projects WHERE id=?", (pid,), one=True)["brief"]
    if old != brief: db.x("INSERT INTO brief_history(project_id,brief,note,ts) VALUES(?,?,?,?)", (pid, old, note, db.now()))
    db.x("UPDATE projects SET brief=?, updated=? WHERE id=?", (brief, db.now(), pid))

def propose(pid, new_brief, reason):
    db.x("UPDATE projects SET pending_brief=?, pending_reason=? WHERE id=?", (new_brief, reason, pid))

def accept(pid):
    p = db.q("SELECT * FROM projects WHERE id=?", (pid,), one=True)
    if p and p["pending_brief"]:
        update_brief(pid, p["pending_brief"], "Accepted suggestion: " + (p["pending_reason"] or ""))
        db.x("UPDATE projects SET pending_brief=NULL, pending_reason=NULL WHERE id=?", (pid,))

def reject(pid): db.x("UPDATE projects SET pending_brief=NULL, pending_reason=NULL WHERE id=?", (pid,))

def restore(pid, hid):
    h = db.q("SELECT * FROM brief_history WHERE id=? AND project_id=?", (hid, pid), one=True)
    if h: update_brief(pid, h["brief"], "Restored an earlier version")

def suggest_update(pid):
    p = get(pid); last = db.q("SELECT ts FROM brief_history WHERE project_id=? ORDER BY ts DESC LIMIT 1", (pid,), one=True)
    since = last["ts"] if last else 0
    items = [i for i in p["items"] if i["ts"] > since]
    if not items and not p["brief"]: raise ValueError("Nothing has been decided since the last revision.")
    ctx = "\n".join(f"- {i['kind']}{' (done)' if i['done'] else ''}: {i['text']}" for i in items) or "(nothing new)"
    raw = llm.text([{"role": "user", "content": f"Revise this project brief to reflect what has been decided since its last revision. Keep it short, in plain lines. Reply with JSON only: "
                     f'{{"brief":"the full revised brief","reason":"one sentence on why"}}.\n\nProject: {p["name"]}\nGoal: {p["goal"]}\nCurrent brief:\n{p["brief"]}\n\nNew since last revision:\n{ctx}'}], feature="brief")
    d = llm.json_from(raw)
    if not isinstance(d, dict) or not d.get("brief"): raise ValueError("The model didn't return a revised brief.")
    propose(pid, str(d["brief"]), str(d.get("reason", "Reflects recent decisions")))
    return get(pid)

def add_link(pid, url, kind=None):
    url = url.strip(); gh = re.match(r"https?://github\.com/([\w.\-]+/[\w.\-]+)", url)
    kind = kind or ("github" if gh else "url")
    if not gh: sources.safe_url(url)
    return db.x("INSERT INTO project_links(project_id,kind,url) VALUES(?,?,?)", (pid, kind, url))

def sync_github(link_id):
    """Read-only sync of README + manifests; private repo content stays local-only."""
    l = db.q("SELECT * FROM project_links WHERE id=?", (link_id,), one=True)
    m = re.match(r"https?://github\.com/([\w.\-]+/[\w.\-]+)", l["url"])
    if not m: raise ValueError("Not a GitHub repo link.")
    repo = m.group(1).removesuffix(".git"); hdr = {"Accept": "application/vnd.github+json", "User-Agent": sources.UA}
    tok = db.get_setting("github_token")
    if tok: hdr["Authorization"] = f"Bearer {tok}"
    r = httpx.get(f"https://api.github.com/repos/{repo}", headers=hdr, timeout=20)
    if r.status_code == 404: raise ValueError("Repo not found. For a private repo add a GitHub token in Settings.")
    r.raise_for_status(); private = 1 if r.json().get("private") else 0
    sid = db.q("SELECT id FROM sources WHERE name=? AND system=1", (f"Repo docs: {repo}",), one=True)
    sid = sid["id"] if sid else db.x("INSERT INTO sources(kind,name,enabled,system,created) VALUES('manual',?,0,1,?)", (f"Repo docs: {repo}", db.now()))
    added, deps = 0, set()
    for path in ("README.md", "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "Package.swift"):
        rr = httpx.get(f"https://api.github.com/repos/{repo}/contents/{path}", headers={**hdr, "Accept": "application/vnd.github.raw+json"}, timeout=20)
        if rr.status_code != 200: continue
        txt = rr.text
        if path != "README.md":
            if path == "package.json":
                try: deps |= set(json.loads(txt).get("dependencies", {}).keys()) | set(json.loads(txt).get("devDependencies", {}).keys())
                except Exception: pass
            elif path == "requirements.txt": deps |= {re.split(r"[=<>~\[ ]", l.strip())[0] for l in txt.splitlines() if l.strip() and not l.startswith("#")}
        url = f"https://github.com/{repo}/blob/HEAD/{path}"
        if not db.q("SELECT 1 FROM articles WHERE url=?", (url,)):
            db.x("INSERT INTO articles(source_id,url,title,published,teaser,text,full_text,created,private,project_id) VALUES(?,?,?,?,?,?,1,?,?,?)",
                 (sid, url, f"{repo}: {path}", db.now(), txt[:600], txt[:30000], db.now(), private, l["project_id"])); added += 1
    from . import graph
    for d in sorted(deps)[:40]:
        tid = graph.resolve(d, "library")
        if tid: graph.pin(tid, l["project_id"])
    db.x("UPDATE project_links SET private=?, synced=?, note=? WHERE id=?", (private, db.now(), f"{added} new doc(s), {len(deps)} dependencies", link_id))
    return {"added": added, "dependencies": len(deps), "private": bool(private)}
