"""A memo or a project's implications as something to paste into Confluence (or anywhere): rich HTML for the clipboard, Markdown, or Confluence
storage format for the page source editor.

Nothing here talks to the network or holds credentials: it only formats what is already in the library. Private material never goes in:
a project with private links is refused outright, and a citation of a private article is left out (the page says how many were)."""
import html, re, time
from . import db, implications, memo

DIRECTION = {"accelerates": "Could speed this up", "threatens": "Could undercut part of this", "enables": "Could open something new", "neutral": "Worth knowing"}
STANDING = {"supported": "Holding up so far", "contradicted": "Contradicted since", "open": "Still open"}
COLOUR = {"high": "Green", "medium": "Yellow", "low": "Grey", "supported": "Green", "contradicted": "Red", "open": "Grey", "threatens": "Red", "accelerates": "Green", "enables": "Blue", "neutral": "Grey"}
FORMATS = ("html", "markdown", "confluence")


class Refused(Exception):
    """This can't be shared (it is private)."""


class _Doc:
    """Title, sections of points, and numbered sources that the points cite."""
    def __init__(self, title, subtitle=""):
        self.title, self.subtitle, self.sections, self.sources, self._n, self.left_out, self.note = title, subtitle, [], [], {}, 0, ""

    def cite(self, dev_ids, rows):
        out = []
        for i in dev_ids:
            r = rows.get(i)
            if not r: continue
            if r.get("private"): self.left_out += 1; continue
            key = r["url"] or f"article-{r['article_id']}"
            if key not in self._n:
                self._n[key] = len(self.sources) + 1
                self.sources.append({"n": self._n[key], "title": r["title"] or r["source"], "url": r["url"] or "", "source": r["source"] or "", "evidence": r.get("evidence", "")})
            if self._n[key] not in out: out.append(self._n[key])
        return out

    def section(self, heading, points):
        if points: self.sections.append({"heading": heading, "points": points})


def _devs(ids):
    ids = list(ids)
    if not ids: return {}
    return {r["id"]: r for r in db.q(f"SELECT d.id,d.evidence,d.article_id,a.title,a.url,a.private,s.name source FROM developments d JOIN articles a ON a.id=d.article_id "
                                      f"JOIN sources s ON s.id=a.source_id WHERE d.id IN ({','.join('?' * len(ids))})", ids)}


def memo_doc(mid):
    m = memo.get(mid)
    if not m: raise LookupError("No such memo.")
    year, week = m["week"].split("-W")
    d = _Doc(f"Strategy memo — week {int(week)}, {year}",
             f"{time.strftime('%d %b', time.localtime(m['since']))} to {time.strftime('%d %b %Y', time.localtime(m['until']))} · from {m['considered']} checked developments")
    rows = _devs({i for k in memo.SECTIONS for p in m[k] for i in p["evidence"]})
    for k, head in (("shifted", "What shifted"), ("projects", "What it may mean for our projects"), ("watch", "What to watch next week"), ("questions", "Open questions")):
        d.section(head, [{"lead": p.get("project", ""), "text": p["text"], "badges": [("strong wording, thin evidence", "Yellow")] if p.get("caution") else [],
                          "cite": d.cite(p["evidence"], rows)} for p in m[k]])
    d.section("How earlier calls are holding up", [{"lead": s["headline"], "text": s["project"], "badges": [(STANDING[s["verdict"]], COLOUR[s["verdict"]])], "cite": []}
                                                   for s in m.get("standing") or []])
    d.note = "Written by SmartWard from public sources. These are possibilities to weigh, not predictions; every point cites the developments it rests on."
    return d


def project_doc(pid):
    p = db.q("SELECT * FROM projects WHERE id=?", (pid,), one=True)
    if not p: raise LookupError("No such project.")
    if db.q("SELECT 1 FROM project_links WHERE project_id=? AND private=1 LIMIT 1", (pid,)): raise Refused("This project has private links, so its implications are not shared.")
    lst = implications.listing(pid)
    hyps = [h for h in lst["hypotheses"] if h["status"] in ("new", "accepted")]
    rows = _devs({i for h in hyps for i in h["evidence"] + h["counter"] + ((h["standing"] or {}).get("supports", []) + (h["standing"] or {}).get("contradicts", []))})
    d = _Doc(f"{p['name']}: what recent developments may mean", p["goal"] or "")
    def point(h):
        st = h["standing"]; badges = [(DIRECTION.get(h["direction"], h["direction"]), COLOUR.get(h["direction"], "Grey")), (f"{h['confidence']} confidence", COLOUR.get(h["confidence"], "Grey"))]
        if st: badges.append((STANDING[st["verdict"]], COLOUR[st["verdict"]]))
        extra = []
        if h["falsifier"]: extra.append(("What would change our mind", h["falsifier"]))
        if h["action"]: extra.append(("A small next step", h["action"]))
        against = d.cite(h["counter"] + (st["contradicts"] if st else []), rows)
        if against: extra.append(("Evidence against", ", ".join(f"[{n}]" for n in against)))
        return {"lead": h["headline"], "text": h["implication"], "badges": badges, "cite": d.cite(h["evidence"] + (st["supports"] if st else []), rows), "extra": extra}
    d.section("Accepted", [point(h) for h in hyps if h["status"] == "accepted"])
    d.section("Under review", [point(h) for h in hyps if h["status"] == "new"])
    if not d.sections: raise LookupError("This project has no implications to share yet.")
    d.note = "Hypotheses from SmartWard, each with its evidence. Not conclusions: confidence is capped by what the evidence can bear."
    return d


# ---------- renderers ----------
E = lambda t: html.escape(str(t or ""), quote=True)
_SAFE_URL = re.compile(r"^https?://", re.I)


def _href(u): return E(u) if _SAFE_URL.match(u or "") else ""


def to_html(d, confluence=False):
    def badge(text, colour):
        if confluence: return f'<ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">{E(colour)}</ac:parameter><ac:parameter ac:name="title">{E(text)}</ac:parameter></ac:structured-macro>'
        return f"<code>{E(text)}</code>"
    out = [f"<h1>{E(d.title)}</h1>"] + ([f"<p><em>{E(d.subtitle)}</em></p>"] if d.subtitle else [])
    for s in d.sections:
        out.append(f"<h2>{E(s['heading'])}</h2><ul>")
        for p in s["points"]:
            li = (f"<strong>{E(p['lead'])}</strong>: " if p["lead"] else "") + E(p["text"])
            li += "".join(" " + badge(t, c) for t, c in p["badges"])
            li += "".join(f'<sup><a href="#src-{n}">[{n}]</a></sup>' if not confluence else f"<sup>[{n}]</sup>" for n in p["cite"])
            if p.get("extra"): li += "<br/>" + "<br/>".join(f"<em>{E(k)}:</em> {E(v)}" for k, v in p["extra"])
            out.append(f"<li>{li}</li>")
        out.append("</ul>")
    if d.sources:
        out.append("<h2>Sources</h2><ol>")
        for s in d.sources:
            title = f'<a href="{_href(s["url"])}">{E(s["title"])}</a>' if _href(s["url"]) else E(s["title"])
            out.append(f'<li id="src-{s["n"]}">{title} — {E(s["source"])}{" (measured)" if s["evidence"] == "measured" else ""}</li>')
        out.append("</ol>")
    out.append(f"<p><em>{E(d.note)}{_left_out(d)}</em></p>")
    return "\n".join(out)


def _md(t): return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", str(t or ""))


def to_markdown(d):
    out = [f"# {_md(d.title)}", ""] + ([f"_{_md(d.subtitle)}_", ""] if d.subtitle else [])
    for s in d.sections:
        out += [f"## {_md(s['heading'])}", ""]
        for p in s["points"]:
            line = "- " + (f"**{_md(p['lead'])}**: " if p["lead"] else "") + _md(p["text"])
            line += "".join(f" `{t}`" for t, _ in p["badges"]) + "".join(f" [{n}]" for n in p["cite"])
            out.append(line)
            out += [f"  - _{_md(k)}:_ {_md(v)}" for k, v in p.get("extra", [])]
        out.append("")
    if d.sources:
        out += ["## Sources", ""] + [f"{s['n']}. " + (f"[{_md(s['title'])}](<{s['url']}>)" if _SAFE_URL.match(s["url"]) else _md(s["title"])) + f" — {_md(s['source'])}" + (" (measured)" if s["evidence"] == "measured" else "") for s in d.sources] + [""]
    out.append(f"_{_md(d.note)}{_md(_left_out(d))}_")
    return "\n".join(out) + "\n"


def _left_out(d): return f" {d.left_out} private citation{'s were' if d.left_out != 1 else ' was'} left out." if d.left_out else ""


def render(kind, ident, fmt="html"):
    if fmt not in FORMATS: raise ValueError("Unknown format.")
    d = memo_doc(ident) if kind == "memo" else project_doc(ident) if kind == "project" else None
    if d is None: raise LookupError("Nothing to share there.")
    content = to_markdown(d) if fmt == "markdown" else to_html(d, confluence=fmt == "confluence")
    slug = re.sub(r"[^a-z0-9]+", "-", d.title.lower()).strip("-")[:60] or "smartward"
    return {"title": d.title, "format": fmt, "content": content, "filename": slug + {"html": ".html", "markdown": ".md", "confluence": ".confluence.xml"}[fmt], "left_out": d.left_out}
