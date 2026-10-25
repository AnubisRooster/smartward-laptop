"""LLM + embedding access (Ollama by default, any litellm model via the `model` setting)."""
import json, math, re, struct
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

def pick_model(private=False, feature="chat"):
    """Background work falls back to the local model once the cloud budget is spent; private never leaves.
    An OpenRouter model answers chat only, unless Settings says "everything": free models are rate-limited and may keep what they are sent."""
    model = db.get_setting("model")
    if model.startswith("openrouter/") and feature != "chat" and (db.get_setting("cloud_scope") or "chat") == "chat":
        return db.DEFAULTS["model"] if _is_local(db.DEFAULTS["model"]) else "ollama_chat/llama3.2:3b"
    if not _is_local(model) and (private or budget_left() <= 0):
        return db.DEFAULTS["model"] if _is_local(db.DEFAULTS["model"]) else "ollama_chat/llama3.2:3b"
    return model

def chat(messages, feature="chat", private=False, tools=None, tool_choice=None, model=None, temperature=0.3, timeout=300):
    from litellm import completion
    model = model or pick_model(private, feature)
    kw = _kwargs(model)
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
