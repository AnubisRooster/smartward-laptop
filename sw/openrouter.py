"""OpenRouter: the list of models that cost nothing. The list is public, so it needs no key; using a model needs one (Settings → Model)."""
import re, time
import httpx

URL = "https://openrouter.ai/api/v1/models"
PREFIX = "openrouter/"
_cache = {"at": 0.0, "models": []}
TTL = 600


def _free(m):
    try:
        p = m.get("pricing") or {}
        if float(p.get("prompt", 1)) != 0 or float(p.get("completion", 1)) != 0: return False
    except (TypeError, ValueError): return False
    out = ((m.get("architecture") or {}).get("output_modalities")) or ["text"]
    if re.search(r"safety|guard", m.get("id", ""), re.I): return False       # classifiers, not chat models
    return list(out) == ["text"]            # chat models; not the music or image generators that are free in preview


def parse(payload):
    """Free text models, longest context first."""
    rows = []
    for m in payload.get("data", []):
        if not m.get("id") or not _free(m): continue
        rows.append({"id": m["id"], "model": PREFIX + m["id"], "name": m.get("name") or m["id"], "context": int(m.get("context_length") or 0),
                     "tools": "tools" in (m.get("supported_parameters") or []), "description": (m.get("description") or "")[:300]})
    rows.sort(key=lambda r: (-r["context"], r["name"].lower()))
    return rows


def free_models(force=False):
    if not force and _cache["models"] and time.time() - _cache["at"] < TTL: return _cache["models"]
    r = httpx.get(URL, timeout=20, headers={"Accept": "application/json"}); r.raise_for_status()
    _cache.update(at=time.time(), models=parse(r.json()))
    return _cache["models"]


def reset(): _cache.update(at=0.0, models=[])
