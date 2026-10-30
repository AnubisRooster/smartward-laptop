"""LLM + embedding access (Ollama by default, any litellm model via the `model` setting)."""
import json, math, re, struct, time
import httpx
from . import db

def _is_local(model): return model.startswith("ollama")

def budget_left():
    spent = q_spent_today()
    return float(db.get_setting("daily_budget") or 0) - spent

def q_spent_today():
    import time
    start = time.time() - 86400
    r = db.q("SELECT COALESCE(SUM(cost),0) c FROM usage WHERE ts>? AND local=0", (start,), one=True)
    return r["c"]

def _log(feature, model, resp):
    from litellm import completion_cost
    u = getattr(resp, "usage", None)
    ti = getattr(u, "prompt_tokens", 0) or 0; to = getattr(u, "completion_tokens", 0) or 0
    cost = 0.0
    if not _is_local(model) and not model.endswith(":free"):
        try: cost = float(completion_cost(completion_response=resp) or 0)
        except Exception: cost = 0.0
    db.x("INSERT INTO usage(ts,feature,model,tokens_in,tokens_out,cost,local) VALUES(?,?,?,?,?,?,?)",
         (db.now(), feature, model, ti, to, cost, 1 if _is_local(model) else 0))

def _kwargs(model):
    kw = {"model": model}
    if _is_local(model): kw["api_base"] = db.get_setting("ollama_base")
    elif db.get_setting("api_key"): kw["api_key"] = db.get_setting("api_key")
    return kw

ANALYSIS_FEATURES = {"graph", "developments", "implications", "analysis"}     # reading articles for what they mean, as opposed to summaries and the daily digest

def _local(): return db.DEFAULTS["model"] if _is_local(db.DEFAULTS["model"]) else "ollama_chat/llama3.2:3b"

def analysis_models():
    """The models used to read public articles for what they mean: a fast, pinned one first, then its fallbacks."""
    first = db.get_setting("analysis_model") or ""
    return [m for m in ([first] + list(db.get_setting("analysis_fallbacks") or [])) if m]

def pick_model(private=False, feature="chat"):
    """Background work falls back to the local model once the cloud budget is spent; private never leaves.
    Chat uses the chosen model. Reading public articles for analysis uses the separate analysis model when the cloud scope allows it (and a key is set);
    "chat only" keeps analysis local, and "everything" also sends summaries and digests. Free models are rate-limited and may keep what they are sent,
    which is why private content never goes."""
    model = db.get_setting("model"); scope = db.get_setting("cloud_scope") or "analysis"
    if feature in ANALYSIS_FEATURES and not private and scope in ("analysis", "everything") and db.get_setting("api_key") and analysis_models() and budget_left() > 0:
        return analysis_models()[0]
    if model.startswith("openrouter/") and feature != "chat":
        if not (scope == "everything" or (scope == "analysis" and feature in ANALYSIS_FEATURES)): return _local()
    if not _is_local(model) and (private or budget_left() <= 0): return _local()
    return model

def _why(e):
    """A short, safe reason from a provider error: no keys, no account ids."""
    t = re.sub(r"\s+", " ", str(e)); t = re.sub(r'"user_id"\s*:\s*"[^"]*"', "", t); t = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "•••", t)
    k = db.get_setting("api_key")
    if k: t = t.replace(k, "•••")
    return f"{type(e).__name__}: {t[-200:]}"


class Unavailable(Exception):
    """Every analysis model in the chain is busy or limited right now. Not the article's fault: try again later without counting a failure."""

RETRYABLE = re.compile(r"rate.?limit|429|timeout|timed out|overloaded|503|502|500|unavailable|APIError|bad.?gateway|no endpoints|not ?found|404", re.I)

def chat(messages, feature="chat", private=False, tools=None, tool_choice=None, model=None, temperature=0.3, timeout=300):
    from litellm import completion
    model = model or pick_model(private, feature)
    chain = analysis_models() if (feature in ANALYSIS_FEATURES and model in analysis_models()) else [model]
    last = None
    for rnd in range(2 if len(chain) > 1 else 1):      # the whole chain once, and if every model was busy, once more after a pause
        for i, m in enumerate(chain):                  # the analysis model, then its fallbacks; anything else has just itself
            try: return _chat_once(completion, messages, feature, m, tools, tool_choice, temperature, timeout)
            except Exception as e:
                last = e
                if not RETRYABLE.search(f"{type(e).__name__} {e}"): raise
                time.sleep(min(4, 1 + i))              # a short breath before the next one, so a burst of limits doesn't hammer them all
        if rnd == 0 and len(chain) > 1: time.sleep(6)
    if feature in ANALYSIS_FEATURES: raise Unavailable(f"The analysis model is busy or rate-limited: {_why(last)}") from last
    raise last

def _chat_once(completion, messages, feature, model, tools, tool_choice, temperature, timeout):
    kw = _kwargs(model)
    if feature in ANALYSIS_FEATURES: kw["max_tokens"] = 3000     # models that think first need room to finish their answer
    if tools: kw["tools"] = tools; kw["tool_choice"] = tool_choice or "auto"
    try: resp = completion(messages=messages, temperature=temperature, timeout=timeout, **kw)
    except Exception as e:
        if not tools or not re.search(r"tool|function", str(e), re.I): raise
        kw.pop("tools", None); kw.pop("tool_choice", None)      # some models (many free ones) can't call tools: answer without them
        resp = completion(messages=messages, temperature=temperature, timeout=timeout, **kw)
    _log(feature, model, resp)
    return resp.choices[0].message

def text(messages, feature="chat", **kw):
    return (chat(messages, feature, **kw).content or "").strip()

def stream(messages, feature="chat", private=False, model=None):
    from litellm import completion
    model = model or pick_model(private, feature)
    resp = completion(messages=messages, stream=True, temperature=0.4, **_kwargs(model))
    for part in resp:
        d = part.choices[0].delta
        if getattr(d, "content", None): yield d.content
    db.x("INSERT INTO usage(ts,feature,model,tokens_in,tokens_out,cost,local) VALUES(?,?,?,0,0,0,?)",
         (db.now(), feature, model, 1 if _is_local(model) else 0))

def json_from(txt):
    """Pull the first JSON object/array out of an LLM reply (models wrap it in prose/fences)."""
    if not txt: return None
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M)
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = txt.find(open_c), txt.rfind(close_c)
        if s != -1 and e > s:
            try: return json.loads(txt[s:e + 1])
            except Exception: continue
    return None

# --- embeddings ---
def embed(texts):
    """Returns list of float lists (unit length) or None if the embedding model is unavailable."""
    if not texts: return []
    try:
        r = httpx.post(db.get_setting("ollama_base").rstrip("/") + "/api/embed",
                       json={"model": db.get_setting("embed_model"), "input": [t[:2000] for t in texts]}, timeout=120)
        r.raise_for_status()
        out = []
        for v in r.json()["embeddings"]:
            n = math.sqrt(sum(a * a for a in v)) or 1.0
            out.append([a / n for a in v])
        return out
    except Exception:
        return None

def pack(v): return struct.pack(f"{len(v)}f", *v)
def unpack(b): return list(struct.unpack(f"{len(b)//4}f", b)) if b else None
