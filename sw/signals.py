"""Signals from time and structure: what is rising, cooling, new, broad, converging, and how far along an idea is.

No model is used. Everything is counted from articles, mentions and sources, so it can be tested, explained, and re-run for any past date.
The one thing it is careful about is *like-for-like*: a feed that was added yesterday and only goes back two weeks would otherwise look like a
sudden surge. Rates are compared only across sources whose history covers the baseline ("covering" sources), and the answer says how much
of the picture that is."""
import json, math, re
from collections import defaultdict
from itertools import combinations
from . import db

DAY = 86400
WEEK = 7 * DAY
RECENT_DAYS = 14                    # "now"
BASE_DAYS = 42                      # what it is compared with: the 6 weeks before that
MIN_RECENT = 3                      # fewer articles than this is never a trend
GENERIC = {"ai", "llm", "llms", "python", "machine learning", "artificial intelligence", "gpu", "software", "openai", "anthropic", "google", "meta", "microsoft", "nvidia"}
LABS = ("openai", "deepmind", "google research", "anthropic", "nvidia", "microsoft research", "hugging face", "together ai", "databricks", "allen institute", "meta ai", "mistral", "cohere")
LADDER = ["paper", "release", "lab", "blog"]       # how an idea usually travels, with "blog" meaning commentary and adoption chatter

DEFAULT_DOMAINS = [
    ("Inference serving", ["vllm", "sglang", "tgi", "inference engine", "continuous batching", "paged attention", "serving", "throughput", "tensorrt"]),
    ("KV cache", ["kv cache", "kv-cache", "prefix caching", "paged attention", "cache eviction", "context compression"]),
    ("Speculative decoding", ["speculative decoding", "speculative", "eagle", "medusa", "draft model", "lookahead decoding"]),
    ("Local & CPU inference", ["llama.cpp", "ollama", "gguf", "quantization", "quantized", "on-device", "cpu inference", "mlx", "int4", "int8"]),
    ("Knowledge graphs & retrieval", ["knowledge graph", "graphrag", "retrieval-augmented", "rag ", "vector search", "embedding"]),
    ("Enterprise AI", ["enterprise", "governance", "compliance", "agentic", "ai agents", "total cost", "roi"]),
    ("Frontier models", ["gpt-", "claude", "gemini", "llama 4", "open weights", "frontier model", "fable", "qwen", "deepseek"]),
]


# ---------- domains (what "our domains" means) ----------
def seed_domains():
    if db.q("SELECT 1 FROM domains LIMIT 1"): return
    for name, kws in DEFAULT_DOMAINS:
        db.x("INSERT INTO domains(name,keywords,created) VALUES(?,?,?)", (name, json.dumps(kws), db.now()))


def domains():
    seed_domains()
    out = db.q("SELECT * FROM domains ORDER BY id")
    for d in out: d["keywords"] = json.loads(d["keywords"] or "[]")
    return out


# ---------- small pure helpers ----------
def source_class(kind, name=""):
    n = (name or "").lower()
    if kind in ("arxiv", "hf_papers"): return "paper"
    if kind == "github": return "release"
    if kind == "rss" and any(l in n for l in LABS): return "lab"
    return "blog"


def keyword_regex(keywords):
    parts = [(r"\b" + re.escape(k.strip().lower()) + (r"\b" if k.strip()[-1:].isalnum() else "")) for k in keywords if k.strip()]
    return re.compile("|".join(parts)) if parts else None


def surprise(observed, base_count, n_recent, n_base):   # kept for callers that only have totals
    """How far the recent count is from what the baseline rate predicts, in rough standard deviations (Poisson, smoothed)."""
    expected = n_recent * (base_count + 0.5) / (n_base + 1.0)
    return (observed - expected) / math.sqrt(expected + 1.0), expected


def label(first_seen, recent_start, obs, base, score, n_recent, sources, expected=0.0):
    if base >= 6 and expected >= 3 and obs <= 0.4 * expected and score <= -1.5 and n_recent >= 20: return "cooling"      # it used to come up often and has gone quiet (obs can be zero here)
    if obs < MIN_RECENT: return "quiet"
    if first_seen is not None and first_seen >= recent_start and sources >= 2: return "emerging"
    if score >= 2.0: return "rising"
    return "steady"


def weekly(ts_list, now, weeks=8):
    out = [0] * weeks
    for t in ts_list:
        i = int((now - t) // WEEK)
        if 0 <= i < weeks: out[weeks - 1 - i] += 1
    return out


class _Dsu:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x: self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


# ---------- the engine ----------
def load(now):
    """Everything needed, once: articles (with source), which themes each mentions, and theme names."""
    lo, hi = now - 400 * DAY, now + DAY           # a few feeds carry impossible dates
    arts = {a["id"]: a for a in db.q(
        "SELECT a.id,a.title,a.teaser,a.published,a.source_id,a.graph_done,a.relevance,s.kind skind,s.name sname FROM articles a JOIN sources s ON s.id=a.source_id "
        "WHERE a.published BETWEEN ? AND ?", (lo, hi))}
    for a in arts.values(): a["cls"] = source_class(a["skind"], a["sname"]); a["text"] = ((a["title"] or "") + " " + (a["teaser"] or "")).lower()
    themes = {t["id"]: t for t in db.q("SELECT id,name,type FROM themes")}
    by_article = defaultdict(set)
    for m in db.q("SELECT article_id,theme_id FROM mentions WHERE source_kind='article'"):
        if m["article_id"] in arts and m["theme_id"] in themes: by_article[m["article_id"]].add(m["theme_id"])
    return arts, themes, by_article


MIN_BASE_DAYS = 14          # a source needs this much of the baseline period to say what is normal for it
MIN_BASE_TOTAL = 5


def source_totals(arts, now):
    """Per source: how much of the baseline it covers and how many articles it published in each period. Rates are compared source by source,
    so a feed that was added yesterday (or one capped at its newest 40 posts) is judged only over the time it actually covers."""
    recent_start, base_start = now - RECENT_DAYS * DAY, now - (RECENT_DAYS + BASE_DAYS) * DAY
    out = {}
    for a in arts.values():
        t = out.setdefault(a["source_id"], {"first": a["published"], "recent_total": 0, "base_total": 0})
        t["first"] = min(t["first"], a["published"])
        if a["published"] >= recent_start: t["recent_total"] += 1
        elif a["published"] >= base_start: t["base_total"] += 1
    for t in out.values():
        t["base_days"] = max(0.0, min(BASE_DAYS, (recent_start - t["first"]) / DAY))
        t["eligible"] = t["base_days"] >= MIN_BASE_DAYS and t["base_total"] >= MIN_BASE_TOTAL
    return out


def compare(recent_by_src, base_by_src, totals):
    """Observed recent count vs the count the baseline predicts, summed over the sources that can be compared fairly.
    Each source's expected share comes from its own baseline, so differences in feed depth and volume cancel out."""
    obs = exp = 0.0; used = 0
    for sid, t in totals.items():
        if not t["eligible"]: continue
        used += 1; obs += recent_by_src.get(sid, 0); exp += (base_by_src.get(sid, 0) + 0.5) / (t["base_total"] + 1.0) * t["recent_total"]
    return obs, exp, (obs - exp) / math.sqrt(exp + 1.0), used


def analyse(domain=None, now=None, data=None):
    """The signals for one domain (or for everything when domain is None). `data` can be passed to avoid reloading."""
    now = now or db.now(); arts, themes, by_article = data or load(now)
    recent_start, base_start = now - RECENT_DAYS * DAY, now - (RECENT_DAYS + BASE_DAYS) * DAY
    totals = source_totals(arts, now)
    rx = keyword_regex(domain["keywords"]) if domain else None
    pool = {i: a for i, a in arts.items() if rx is None or rx.search(a["text"])}
    recent = {i for i, a in pool.items() if a["published"] >= recent_start}; base = {i for i, a in pool.items() if base_start <= a["published"] < recent_start}
    by_src = lambda ids: _count(pool[i]["source_id"] for i in ids)
    eligible_recent = sum(t["recent_total"] for t in totals.values() if t["eligible"])
    n_recent_all = sum(t["recent_total"] for t in totals.values())
    obs, exp, score, used = compare(by_src(recent), by_src(base), totals)
    out = {"domain": domain["name"] if domain else "All", "now": now, "window": {"recent_days": RECENT_DAYS, "baseline_days": BASE_DAYS},
           "coverage": {"sources_total": len(totals), "sources_comparable": used, "recent_articles_comparable": eligible_recent,
                        "provisional": used < 4 or eligible_recent < 30},
           "weekly": weekly([a["published"] for a in pool.values()], now)}
    first = min((a["published"] for a in pool.values()), default=None)
    out["momentum"] = {"recent": len(recent), "baseline": len(base), "observed_comparable": round(obs, 1), "expected": round(exp, 1), "score": round(score, 2),
                       "label": label(first, recent_start, int(obs), len(base), score, eligible_recent, len({pool[i]["source_id"] for i in recent}), exp) if used else "unknown"}

    # themes inside this domain
    graphed = {i for i in arts if arts[i]["graph_done"]}
    total_graphed = max(1, len(graphed))
    doc_freq = defaultdict(int)
    for i in graphed:
        for t in by_article.get(i, ()): doc_freq[t] += 1
    inside = defaultdict(lambda: {"recent": set(), "base": set(), "all": set()})
    for i in pool:
        for t in by_article.get(i, ()):
            bucket = inside[t]; bucket["all"].add(i)
            if i in recent: bucket["recent"].add(i)
            elif i in base: bucket["base"].add(i)
    first_seen_theme = {}
    for i in graphed:
        for t in by_article.get(i, ()): first_seen_theme[t] = min(first_seen_theme.get(t, now), arts[i]["published"])
    pool_totals = {}
    for sid, t in totals.items():             # a theme is compared with the domain's own articles from the same source
        pr = sum(1 for i in recent if pool[i]["source_id"] == sid); pb = sum(1 for i in base if pool[i]["source_id"] == sid)
        pool_totals[sid] = {"eligible": t["eligible"] and (pb + pr) > 0, "base_total": pb, "recent_total": pr}
    items = []
    for t, b in inside.items():
        th = themes[t]; generic = th["name"].lower() in GENERIC or doc_freq[t] / total_graphed > 0.15
        if generic or len(b["all"]) < 2: continue
        o, e, s_, _ = compare(by_src(b["recent"]), by_src(b["base"]), pool_totals)
        srcs = {pool[i]["source_id"] for i in b["recent"]}; classes = {pool[i]["cls"] for i in b["recent"]}
        lab = label(first_seen_theme.get(t), recent_start, len(b["recent"]), len(b["base"]), s_, eligible_recent, len(srcs), e)
        ev = sorted(b["recent"] or b["all"], key=lambda i: -(pool[i]["published"] or 0))[:5]
        items.append({"theme_id": t, "name": th["name"], "type": th["type"], "label": lab, "recent": len(b["recent"]), "baseline": len(b["base"]), "score": round(s_, 2),
                      "sources": len(srcs), "source_kinds": sorted(classes), "first_seen": first_seen_theme.get(t), "evidence": ev, "ladder": ladder(t, by_article, arts, graphed)})
    for key in ("emerging", "rising", "cooling"):
        out[key] = sorted([x for x in items if x["label"] == key], key=lambda x: (-x["score"] if key != "cooling" else x["score"], -x["recent"]))[:8]
    out["converging"] = convergence(pool, by_article, themes, recent, base, doc_freq, total_graphed)
    out["evidence"] = [i for i in sorted(recent, key=lambda i: -(pool[i]["relevance"] or 0))[:8]]
    return out


def _count(it):
    d = defaultdict(int)
    for x in it: d[x] += 1
    return d


def ladder(theme_id, by_article, arts, graphed):
    """When this idea first showed up as a paper, a release, a lab announcement and as commentary."""
    first = {}
    for i in graphed:
        if theme_id in by_article.get(i, ()):
            a = arts[i]; c = a["cls"]
            if c not in first or a["published"] < first[c][0]: first[c] = (a["published"], i)
    reached = [c for c in LADDER if c in first]
    return {"stages": [{"stage": c, "first": first[c][0], "article_id": first[c][1]} for c in reached],
            "furthest": reached[-1] if reached else None, "next": next((c for c in LADDER if c not in first), None)}


def convergence(pool, by_article, themes, recent, base, doc_freq, total_graphed):
    """Pairs of ideas that had not appeared together before and now do, especially when they came from separate clusters."""
    ok = lambda t: themes[t]["name"].lower() not in GENERIC and doc_freq[t] / total_graphed <= 0.15
    co_recent, co_base, presence = defaultdict(set), defaultdict(int), defaultdict(int)
    for i in pool:
        ts_ = [t for t in by_article.get(i, ()) if ok(t)]
        for t in ts_:
            if i in base: presence[t] += 1
        for a, b in combinations(sorted(ts_), 2):
            if i in recent: co_recent[(a, b)].add(i)
            elif i in base: co_base[(a, b)] += 1
    dsu = _Dsu(); size = defaultdict(int)
    for (a, b), n in co_base.items():
        if n >= 2: dsu.union(a, b)
    for t in presence: size[dsu.find(t)] += 1
    out = []
    for (a, b), ids in co_recent.items():
        if len(ids) < 2 or co_base.get((a, b), 0) > 0 or presence[a] < 2 or presence[b] < 2: continue
        bridge = dsu.find(a) != dsu.find(b) and size[dsu.find(a)] >= 3 and size[dsu.find(b)] >= 3
        out.append({"a": themes[a]["name"], "b": themes[b]["name"], "a_id": a, "b_id": b, "together": len(ids), "bridge": bridge, "evidence": sorted(ids, key=lambda i: -(pool[i]["published"] or 0))[:4]})
    out.sort(key=lambda x: (-x["bridge"], -x["together"]))
    return out[:8]


def overview(now=None):
    now = now or db.now(); data = load(now)
    return [analyse(d, now, data) for d in domains()]
