"""Reference architectures and the checks a reviewer would make of a stack map.

A pattern is the shape most systems of a kind share (an enterprise agent platform, LLM serving, retrieval, hybrid model routing) and the parts a
reviewer expects to find in one. The checker is plain code: it reports parts that connect to nothing, connections that don't say what they do,
cloud models reached around the router, things with no stated place to run, and the parts the pattern expects but the map lacks."""
import re

TYPES = {  # type: what it means (shown in the editor)
    "actor": "a person or outside system that uses the platform", "app": "an application people use", "agent": "an agent or agent runtime",
    "service": "a platform service", "gateway": "a gateway, router or proxy that requests pass through", "datastore": "a database, index or store",
    "model": "a model or model server you run", "external": "a model or service someone else runs (a cloud API)", "infra": "infrastructure: clusters, GPUs, networks",
}

# role: (name, regex over a part's name and words, types that satisfy it, why a reviewer asks)
_ID = ("Identity & policy", r"identit|auth|iam|sso|rbac|polic|guardrail|permission|access control", (), "who may use which agents, models and data; enterprise reviews start here")
_GW = ("Gateway or model router", r"gateway|router|routing|proxy|load balanc", ("gateway",), "one place where requests are authenticated, metered and sent to the right model")
_OBS = ("Observability & evaluation", r"observab|monitor|tracing|telemetry|logging|metric|eval", (), "traces, costs and quality checks; without them nobody can tell if it works")
_STORE = ("Knowledge or retrieval store", r"vector|retriev|rag\b|knowledge|memory|database|index|store", ("datastore",), "agents need company data and memory, kept somewhere governed")
_REG = ("Tool & skill registry", r"registr|mcp|tool|skill|catalog|plugin", (), "where agents find approved tools and skills, and where new skills are reviewed")
_MODEL = ("Models (served here or by a provider)", r"model|llm|vllm|sglang|bedrock|azure openai|serving", ("model", "external"), "the models the platform actually calls")
_SANDBOX = ("Sandbox for running code", r"sandbox|isolat|gvisor|firecracker|container runtime|execution env", (), "a coding agent runs code it wrote; that needs an isolated place")

PATTERNS = {
    "agent_platform": {"title": "Enterprise agent platform", "select": ["agent", "harness", "control plane", "skill", "copilot", "platform", "assistant"],
                       "roles": [_ID, _GW, _OBS, _STORE, _REG, _MODEL], "if": [(r"coding agent|code gen|code execution|autonomous coding", _SANDBOX)]},
    "llm_serving": {"title": "LLM serving", "select": ["vllm", "sglang", "serving", "inference", "kv cache", "throughput", "latency", "speculative"],
                    "roles": [_GW, ("Scheduler / batching", r"schedul|batch|queue", (), "how requests share the GPUs decides throughput and latency"),
                              ("Model server", r"vllm|sglang|tgi|tensorrt|llama\.cpp|serv|engine", ("model",), "the engine that runs the model"),
                              ("KV cache / memory", r"kv|cache|memory|offload", (), "the main limit on concurrency and context length"),
                              ("Accelerators", r"gpu|accelerat|hardware|cpu|npu", ("infra",), "what it runs on sets cost and speed"), _OBS], "if": []},
    "rag": {"title": "Retrieval-augmented generation", "select": ["rag", "retrieval", "knowledge graph", "search", "embedding", "documents"],
            "roles": [("Ingestion", r"ingest|crawl|connector|pipeline|sync|parse", (), "how documents get in and stay current"),
                      ("Embeddings", r"embed", (), "turns text into vectors"), ("Index / vector store", r"vector|index|search|store", ("datastore",), "where retrieval looks"),
                      ("Retriever / reranker", r"retriev|rerank|search", (), "picks what the model sees"), _MODEL,
                      ("Evaluation & feedback", r"eval|feedback|judge|quality", (), "answers must be checked against sources")], "if": []},
    "hybrid_routing": {"title": "Hybrid model routing (own GPUs + cloud)", "select": ["hybrid", "bedrock", "azure", "on-prem", "router", "multi-cloud", "data center"],
                       "roles": [_GW, ("Models served on your own GPUs", r"vllm|sglang|on-prem|self-host|serv", ("model",), "the private, fixed-cost side"),
                                 ("Cloud model providers", r"bedrock|azure|vertex|openai|anthropic|cloud", ("external",), "the frontier side, paid per use"),
                                 _ID, ("Cost & usage metering", r"cost|budget|usage|meter|billing|quota", (), "routing is mostly a cost decision"), _OBS], "if": []},
}


def select(text):
    """The pattern whose words best match a project's description, or None."""
    t = (text or "").lower(); best, score = None, 0
    for key, p in PATTERNS.items():
        s = sum(1 for w in p["select"] if w in t)
        if s > score: best, score = key, s
    return best


def _text(part): return f"{part['label']} {' '.join(part['terms'])}".lower()


def _has(parts, role):
    _, rx, types, _ = role
    return any(p["type"] in types or re.search(rx, _text(p)) for p in parts)


def missing(model):
    """The roles the map's pattern expects that no part fills: [(name, why)]."""
    p = PATTERNS.get(model.get("pattern") or "")
    if not p: return []
    parts = model["parts"]; roles = list(p["roles"])
    for rx, role in p["if"]:
        if any(re.search(rx, _text(x)) for x in parts): roles.append(role)
    return [(r[0], r[3]) for r in roles if not _has(parts, r)]


def check(model, overlay=None):
    """What a reviewer would point out, as [{"level": "warn"|"info", "text"}], most important first."""
    parts, edges = model["parts"], model["edges"]; by = {p["id"]: p for p in parts}; out = []
    deg = {p["id"]: 0 for p in parts}
    for e in edges: deg[e["a"]] += 1; deg[e["b"]] += 1
    for name, why in missing(model):
        out.append({"level": "warn", "text": f"No {name.lower()} — {why}."})
    if len(parts) >= 3:
        for p in parts:
            if not deg[p["id"]]: out.append({"level": "warn", "text": f"“{p['label']}” isn't connected to anything."})
    for e in edges:
        a, b = by[e["a"]], by[e["b"]]
        if b["type"] == "external" and a["type"] not in ("gateway", "external") and not re.search(r"gateway|router|proxy", _text(a)):
            out.append({"level": "warn", "text": f"“{a['label']}” calls “{b['label']}” directly; cloud models usually sit behind the router or gateway."})
    unlabeled = sum(1 for e in edges if not e["verb"])
    if unlabeled: out.append({"level": "info", "text": f"{unlabeled} connection{'s don' if unlabeled != 1 else ' doesn'}'t say what flows (add “: verb”, e.g. “-> Router: routes prompts”)."})
    for p in parts:
        if deg[p["id"]] > 6: out.append({"level": "info", "text": f"“{p['label']}” connects to {deg[p['id']]} parts; consider splitting it or grouping what it manages."})
    if model.get("zones"):
        homeless = [p["label"] for p in parts if not p["zone"] and p["type"] in ("model", "external", "infra", "datastore")]
        if homeless: out.append({"level": "info", "text": "Say where these run (put them under a [zone]): " + ", ".join(homeless[:5]) + "."})
    seen, shared = {}, []
    for p in parts:
        for w in p["terms"]:
            if w in seen and seen[w] != p["label"] and w not in shared: shared.append(w)
            seen.setdefault(w, p["label"])
    if shared: out.append({"level": "info", "text": "Used on more than one part (evidence counts for both): " + ", ".join(shared[:6]) + "."})
    if overlay is not None:
        quiet = [p["label"] for p in parts if not overlay.get(p["id"], {}).get("development_count")]
        if quiet and len(quiet) == len(parts):
            out.append({"level": "info", "text": "No part matches any recent development yet; use words articles use (products, techniques)."})
        elif quiet:
            out.append({"level": "info", "text": "No recent developments mention: " + ", ".join(quiet[:6]) + ". Use words articles use (products, techniques); the counts are beside each part."})
    return out
