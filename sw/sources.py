"""Source fetchers: RSS/Atom, arXiv, Hugging Face papers, Hacker News, GitHub releases, watched web pages."""
import hashlib, re, threading, time, urllib.robotparser
from calendar import timegm
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin
import httpx
from lxml import etree, html as lhtml
from . import db

UA = "SmartWard/1.0 (+local research reader)"
HOST_GAP = 1.5            # seconds between requests to one host
_last_hit, _hit_lock, _robots = {}, threading.Lock(), {}
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref", "ref_src"}

class FetchError(Exception): pass

def canon(url):
    p = urlparse(url.strip())
    qs = [(k, v) for k, v in parse_qsl(p.query) if k not in TRACKING]
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(qs), ""))

def _wait(host):
    with _hit_lock:
        t = _last_hit.get(host, 0); wait = HOST_GAP - (time.time() - t)
        _last_hit[host] = time.time() + max(wait, 0)
    if wait > 0: time.sleep(wait)

def safe_url(url):
    """Refuse non-http(s), credentials in URLs, and local/metadata hosts (the strategist's fetch_url uses this too)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"): raise FetchError("Only http(s) links are allowed.")
    if p.username or p.password: raise FetchError("Links with credentials are not allowed.")
    h = (p.hostname or "").lower()
    if not h or h in ("localhost", "metadata.google.internal") or h.endswith(".local") or h.endswith(".internal"):
        raise FetchError("That host is not allowed.")
    import ipaddress, socket
    try:
        for info in socket.getaddrinfo(h, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise FetchError("That address is on a private network, so SmartWard won't fetch it.")
    except socket.gaierror:
        raise FetchError("Couldn't find that site (DNS lookup failed).")
    return url

def robots_ok(url):
    p = urlparse(url); base = f"{p.scheme}://{p.netloc}"
    rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = httpx.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=10, follow_redirects=True)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception: rp.parse([])
        _robots[base] = rp
    return rp.can_fetch(UA, url)

def _redirects(r):
    """True only for a redirect that says where to go. A 304 (not modified) is a 3xx too, but it is an answer, not a redirect."""
    return r.status_code in (301, 302, 303, 307, 308) and "location" in r.headers

def get(url, etag=None, last_modified=None, check_robots=False, tries=3):
    safe_url(url)
    if check_robots and not robots_ok(url): raise FetchError("The site's robots.txt asks automated readers to stay away.")
    host = urlparse(url).netloc
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    if etag: hdr["If-None-Match"] = etag
    if last_modified: hdr["If-Modified-Since"] = last_modified
    delay = 2
    for i in range(tries):
        _wait(host)
        try:
            with httpx.Client(follow_redirects=False, timeout=25, headers=hdr) as c:
                r = c.get(url); hops = 0
                while _redirects(r) and hops < 4:                       # follow redirects only to safe public hosts
                    nxt = urljoin(str(r.url), r.headers["location"]); safe_url(nxt); r = c.get(nxt); hops += 1
                if _redirects(r): raise FetchError("Too many redirects.")
        except FetchError: raise
        except httpx.TimeoutException: raise FetchError("The site took too long to answer.")
        except httpx.HTTPError as e: raise FetchError(f"Network problem: {e.__class__.__name__}")
        if r.status_code in (429, 503) and i < tries - 1:
            time.sleep(min(delay, float(r.headers.get("retry-after", delay)) if r.headers.get("retry-after", "").isdigit() else delay)); delay *= 2; continue
        if r.status_code == 304: return r
        if r.status_code >= 400: raise FetchError(f"The site answered {r.status_code}.")
        return r
    raise FetchError("The site is busy (rate limited). Try again later.")

def _ts(s):
    if not s: return None
    try: return parsedate_to_datetime(s).timestamp()
    except Exception: pass
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d)(?::(\d\d))?)?", s.strip())
    if m:
        y, mo, d, h, mi, se = [int(g) if g else 0 for g in m.groups()]
        try: return float(timegm((y, mo, d, h, mi, se)))
        except Exception: return None
    return None

def clean_html(s):
    """HTML -> plain text, dropping scripts/styles and visually hidden text."""
    if not s: return ""
    try:
        doc = lhtml.fromstring(f"<div>{s}</div>")
        for el in doc.xpath("//script|//style|//noscript|//*[@hidden]|//*[contains(@style,'display:none')]|//*[contains(@style,'visibility:hidden')]|//*[@aria-hidden='true']"):
            par = el.getparent()
            if par is None: continue
            if el.tail:                                  # keep the text after the hidden element
                prev = el.getprevious()
                if prev is not None: prev.tail = (prev.tail or "") + el.tail
                else: par.text = (par.text or "") + el.tail
            par.remove(el)
        t = doc.text_content()
    except Exception:
        t = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", t).strip()

def parse_feed(content):
    root = etree.fromstring(content, parser=etree.XMLParser(recover=True, resolve_entities=False, no_network=True))
    if root is None: raise FetchError("That doesn't look like a feed.")
    ns = {"a": "http://www.w3.org/2005/Atom", "c": "http://purl.org/rss/1.0/modules/content/", "dc": "http://purl.org/dc/elements/1.1/"}
    out = []
    for e in root.xpath("//item | //a:entry", namespaces=ns):
        def tx(path):
            r = e.xpath(path, namespaces=ns)
            if not r: return ""
            return (r[0] if isinstance(r[0], str) else (r[0].text or "")).strip()
        link = tx("link/text()") or tx("a:link[@rel='alternate']/@href") or tx("a:link/@href") or tx("guid/text()")
        body = ""
        for p in ("c:encoded", "a:content", "description", "a:summary", "summary"):
            r = e.xpath(p, namespaces=ns)
            if r:
                body = "".join(r[0].itertext()) if len(r[0]) == 0 else etree.tostring(r[0], encoding="unicode")
                body = body or ""
                if body.strip(): break
        out.append({"url": link, "title": clean_html(tx("title/text()") or tx("a:title/text()") or tx("a:title")) or link, "author": clean_html(tx("dc:creator/text()") or tx("a:author/a:name/text()") or tx("author/text()")),
                    "published": _ts(tx("pubDate/text()") or tx("a:published/text()") or tx("a:updated/text()") or tx("dc:date/text()")),
                    "teaser": clean_html(body)[:4000]})
    return [a for a in out if a["url"]]

def discover_feed(url):
    r = get(url); doc = lhtml.fromstring(r.content)
    for l in doc.xpath("//link[@rel='alternate'][contains(@type,'rss') or contains(@type,'atom')]"):
        if l.get("href"): return urljoin(str(r.url), l.get("href"))
    return None

def fetch_source(src):
    """Returns (articles, new_etag, new_last_modified)."""
    kind, url, query = src["kind"], src["url"], src["query"]
    if kind == "rss":
        r = get(url, src.get("etag"), src.get("last_modified"))
        if r.status_code == 304: return [], src.get("etag"), src.get("last_modified")
        arts = parse_feed(r.content)
        if not arts:
            alt = discover_feed(url)
            if alt and alt != url:
                db.x("UPDATE sources SET url=? WHERE id=?", (alt, src["id"]))
                r = get(alt); arts = parse_feed(r.content)
        return arts, r.headers.get("etag"), r.headers.get("last-modified")
    if kind == "arxiv":
        qs = f"cat:{query}" if re.fullmatch(r"[a-z\-]+\.[A-Z]{2}", query or "") else f"all:{query}"
        r = get("https://export.arxiv.org/api/query?" + urlencode({"search_query": qs, "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 30}))
        return parse_feed(r.content), None, None
    if kind == "hf_papers":
        r = get("https://huggingface.co/api/daily_papers"); arts = []
        for it in r.json():
            p = it.get("paper", {})
            if p.get("id"):
                arts.append({"url": f"https://huggingface.co/papers/{p['id']}", "title": p.get("title", ""), "author": ", ".join(a.get("name", "") for a in p.get("authors", [])[:4]),
                             "published": _ts(p.get("publishedAt")), "teaser": p.get("summary", "")[:4000]})
        return arts, None, None
    if kind == "hn":
        r = get("https://hn.algolia.com/api/v1/search_by_date?" + urlencode({"query": query, "tags": "story", "hitsPerPage": 30}))
        arts = []
        for h in r.json().get("hits", []):
            u = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
            arts.append({"url": u, "title": h.get("title") or "", "author": h.get("author"), "published": _ts(h.get("created_at")), "teaser": h.get("story_text") or ""})
        return arts, None, None
    if kind == "github":
        repo = (query or url or "").replace("https://github.com/", "").strip("/")
        if not re.fullmatch(r"[\w.\-]+/[\w.\-]+", repo): raise FetchError("Use owner/repo for GitHub releases.")
        r = get(f"https://github.com/{repo}/releases.atom", src.get("etag"), src.get("last_modified"))
        if r.status_code == 304: return [], src.get("etag"), src.get("last_modified")
        return parse_feed(r.content), r.headers.get("etag"), r.headers.get("last-modified")
    if kind == "web":
        r = get(url, check_robots=True); text, title = extract_page(r.text, str(r.url))
        if not text: raise FetchError("Couldn't read any text from that page.")
        h = hashlib.sha1(text.encode()).hexdigest()[:10]
        return [{"url": canon(url) + "#v" + h, "title": title or url, "author": "", "published": time.time(), "teaser": text[:4000], "text": text}], None, None
    raise FetchError(f"Unknown source type {kind}.")

def extract_page(html_text, url=None):
    import trafilatura
    text = trafilatura.extract(html_text, url=url, include_comments=False) or ""
    meta = trafilatura.extract_metadata(html_text)
    return clean_html(text) if "<" in text else text.strip(), (meta.title if meta else "")

def fetch_full_text(url):
    r = get(url, check_robots=True)
    text, title = extract_page(r.text, str(r.url))
    return text, title

MAX_PER_FETCH = 40      # a feed with years of archive (some publish 1,000+ posts) brings in its newest posts, not all of them

def newest(arts, n=MAX_PER_FETCH):
    return sorted(arts, key=lambda a: -(a.get("published") or 0))[:n]

def refresh_source(sid):
    src = db.q("SELECT * FROM sources WHERE id=?", (sid,), one=True)
    if not src: return 0
    added = 0
    try:
        arts, etag, lm = fetch_source(src)
        for a in newest(arts):
            u = canon(a["url"]) if "#v" not in a["url"] else a["url"]
            if db.q("SELECT 1 FROM articles WHERE url=?", (u,)): continue
            if not a.get("title"): continue
            teaser = a.get("teaser") or ""
            txt = a.get("text") or ""
            db.x("INSERT INTO articles(source_id,url,title,author,published,teaser,text,full_text,created,project_id,stage) VALUES(?,?,?,?,?,?,?,?,?,?,'new')",
                 (sid, u, a["title"][:500], (a.get("author") or "")[:200], a.get("published") or db.now(), teaser, txt, 1 if txt else 0, db.now(), src.get("project_id")))
            added += 1
        db.x("UPDATE sources SET etag=?,last_modified=?,last_status='ok',last_error=NULL,last_fetched=? WHERE id=?", (etag, lm, db.now(), sid))
    except FetchError as e:
        db.x("UPDATE sources SET last_status='error',last_error=?,last_fetched=? WHERE id=?", (str(e), db.now(), sid))
    except Exception as e:
        db.x("UPDATE sources SET last_status='error',last_error=?,last_fetched=? WHERE id=?", (f"Unexpected problem: {e.__class__.__name__}: {e}", db.now(), sid))
    return added

def add_source(kind, name=None, url=None, query=None, project_id=None, system=0):
    """Validates by fetching once; raises FetchError with a human message."""
    if kind in ("rss", "web") and not url: raise FetchError("Enter a link.")
    if kind in ("arxiv", "hn") and not query: raise FetchError("Enter a search or category.")
    if kind == "github":
        query = (query or url or "").replace("https://github.com/", "").strip("/")
        if not re.fullmatch(r"[\w.\-]+/[\w.\-]+", query): raise FetchError("Use owner/repo, like vllm-project/vllm.")
    if url: url = url.strip(); safe_url(url)
    dup = db.q("SELECT id FROM sources WHERE kind=? AND COALESCE(url,'')=? AND COALESCE(query,'')=?", (kind, url or "", query or ""), one=True)
    if dup: return dup["id"]
    default_names = {"rss": url, "web": url, "arxiv": f"arXiv: {query}", "hn": f"Hacker News: {query}", "hf_papers": "Hugging Face daily papers", "github": f"{query} releases"}
    sid = db.x("INSERT INTO sources(kind,name,url,query,project_id,system,created) VALUES(?,?,?,?,?,?,?)",
               (kind, name or default_names.get(kind) or kind, url, query, project_id, system, db.now()))
    refresh_source(sid)
    s = db.q("SELECT * FROM sources WHERE id=?", (sid,), one=True)
    if s["last_status"] == "error":
        err = s["last_error"]; db.x("DELETE FROM sources WHERE id=?", (sid,)); raise FetchError(err)
    if kind == "rss" and not name:
        try:
            r = get(s["url"]); root = etree.fromstring(r.content, parser=etree.XMLParser(recover=True))
            t = root.xpath("string(//channel/title | //*[local-name()='feed']/*[local-name()='title'])").strip()
            if t: db.x("UPDATE sources SET name=? WHERE id=?", (t[:120], sid))
        except Exception: pass
    return sid

def add_page_as_article(url, source_name="Read in chat", project_id=None):
    """A page the strategist read with approval is saved as a real article."""
    src = db.q("SELECT id FROM sources WHERE name=? AND system=1", (source_name,), one=True)
    sid = src["id"] if src else db.x("INSERT INTO sources(kind,name,enabled,system,created) VALUES('manual',?,0,1,?)", (source_name, db.now()))
    text, title = fetch_full_text(url); u = canon(url)
    ex = db.q("SELECT id FROM articles WHERE url=?", (u,), one=True)
    if ex: return ex["id"], text
    aid = db.x("INSERT INTO articles(source_id,url,title,published,teaser,text,full_text,created,project_id) VALUES(?,?,?,?,?,?,1,?,?)",
               (sid, u, title or u, db.now(), text[:600], text, db.now(), project_id))
    return aid, text
