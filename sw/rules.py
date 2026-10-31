"""Best-practice rules for architecture maps, and the weighted score built from them.

Every rule names where it comes from (OWASP Top 10 for LLM Applications 2025 and OWASP's agentic AI threats guidance, the AWS and Azure
Well-Architected guidance for AI workloads, NIST AI RMF 1.0, NIST SP 800-207 zero trust, the C4 model), says why it matters and how to fix it,
and is checked by code over the map: which parts exist, their types and zones, and which way the arrows go. A rule that doesn't apply to a map
(no coding agent, no cloud zone) doesn't count either way. Questions code can't answer (is this arrow plausible? is the brief's constraint
met?) come from a separate reviewer model through a fixed rubric (see maps.review), never as new rules.

The score weights five parts: correctness 25, best practices 35, completeness against the reference pattern 15, fidelity to the brief 15,
evidence from your reading 10. A rule you waive in the map ("@waive S3: secrets are handled by the platform team") counts as met and is listed."""
import re
from . import patterns

WEIGHTS = {"correctness": 25, "practice": 35, "completeness": 15, "fidelity": 15, "evidence": 10}
AREAS = {"correctness": "Correctness", "security": "Security", "data": "Data protection", "governance": "Governance", "reliability": "Reliability",
         "observability": "Observability & cost", "clarity": "Clarity"}

OWASP_LLM = "OWASP Top 10 for LLM Applications 2025"
OWASP_AGENT = "OWASP Agentic AI – Threats and Mitigations"
WAF = "AWS Well-Architected Generative AI Lens / Azure Well-Architected AI workloads"
NIST_RMF = "NIST AI RMF 1.0"
ZT = "NIST SP 800-207 Zero Trust Architecture"
C4 = "C4 model"


# ---------- reading a map ----------
def _t(p): return f"{p['label']} {' '.join(p['terms'])} {p.get('note') or ''}".lower()
def find(m, rx, types=()): return [p for p in m["parts"] if p["type"] in types or (rx and re.search(rx, _t(p)))]
def ins(m, pid, kind=None): return [e for e in m["edges"] if e["b"] == pid and (kind is None or e["kind"] == kind)]
def outs(m, pid, kind=None): return [e for e in m["edges"] if e["a"] == pid and (kind is None or e["kind"] == kind)]
def by_id(m): return {p["id"]: p for p in m["parts"]}

IDENTITY = r"identit|\biam\b|\bsso\b|oidc|oauth|rbac|\bauthz?\b|policy|\bopa\b|access control|entra|okta|keycloak"
GATEWAY = r"gateway|router|routing|proxy|load balanc"
OBS = r"observab|monitor|tracing|traces|telemetry|opentelemetry|langfuse|prometheus|logging|metrics|\beval"
CODING = r"coding agent|code gen|claude code|codex|coding-agent|autonomous coding|swe agent"
SANDBOX = r"sandbox|gvisor|firecracker|isolat|e2b|microvm"
CLOUD_ZONE = r"aws|azure|gcp|google cloud|cloud|saas|openai|anthropic"


def cloud_parts(m):
    zones = {z for z in m["zones"] if re.search(CLOUD_ZONE, z.lower())}
    return [p for p in m["parts"] if p["type"] == "external" or p["zone"] in zones]


def onprem(m): return [p for p in m["parts"] if p not in cloud_parts(m) and p["type"] not in ("actor",)]


# ---------- the rules: (id, area, weight 1-3, title, why, fix, reference, check) ----------
# check(m) -> None (doesn't apply), True (met), or a short string saying what is wrong.
def _r_store_calls(m):
    bad = [by_id(m)[e["a"]]["label"] for e in m["edges"] if by_id(m)[e["a"]]["type"] == "datastore" and e["kind"] == "data"
           and not re.search(r"replicat|sync|stream|publish|emit|notif|event|change", e["verb"].lower())]
    return True if not bad else f"arrows start at {', '.join(sorted(set(bad))[:3])}"

def _r_actor_target(m):
    bad = [by_id(m)[e["b"]]["label"] for e in m["edges"] if by_id(m)[e["b"]]["type"] == "actor" and not re.search(r"notif|alert|report|respon|return|show", e["verb"].lower())]
    return True if not bad else f"{', '.join(sorted(set(bad))[:3])} receive{'s' if len(set(bad)) == 1 else ''} calls"

def _r_infra_calls(m):
    bad = [by_id(m)[e["a"]]["label"] for e in m["edges"] if by_id(m)[e["a"]]["type"] == "infra" and e["kind"] == "data"]
    return True if not bad else f"{', '.join(sorted(set(bad))[:3])} sends data"

def _r_control_from(m):
    bad = [f"{by_id(m)[e['a']]['label']} → {by_id(m)[e['b']]['label']}" for e in m["edges"] if e["kind"] == "control" and by_id(m)[e["a"]]["type"] in ("datastore", "actor", "external", "model")]
    return True if not bad else "; ".join(bad[:3])

def _r_labels(m):
    if not m["edges"]: return None
    bad = sum(1 for e in m["edges"] if not e["verb"])
    return True if not bad else f"{bad} unlabelled"

def _r_cross_zone_protocol(m):
    z = {p["id"]: p["zone"] for p in m["parts"]}
    cross = [e for e in m["edges"] if z[e["a"]] != z[e["b"]] and z[e["a"]] and z[e["b"]]]
    if not cross: return None
    bad = [f"{by_id(m)[e['a']]['label']} → {by_id(m)[e['b']]['label']}" for e in cross if not e["protocol"]]
    return True if not bad else "; ".join(bad[:3])

def _r_connected(m):
    if len(m["parts"]) < 3: return None
    bad = [p["label"] for p in m["parts"] if not ins(m, p["id"]) and not outs(m, p["id"])]
    return True if not bad else ", ".join(bad[:4])

def _r_zones(m):
    if not m["zones"]: return "no zones" if len(m["parts"]) >= 6 else None
    bad = [p["label"] for p in m["parts"] if not p["zone"] and p["type"] not in ("actor",)]
    return True if not bad else ", ".join(bad[:4])

def _r_size(m):
    deg = {p["id"]: len(ins(m, p["id"])) + len(outs(m, p["id"])) for p in m["parts"]}
    hubs = [by_id(m)[i]["label"] for i, d in deg.items() if d > 9 and by_id(m)[i]["type"] != "gateway"]
    if len(m["parts"]) > 22: return f"{len(m['parts'])} parts"
    return True if not hubs else f"{', '.join(hubs)} connect{'s' if len(hubs) == 1 else ''} to too much"

def _r_entry_auth(m):
    ids = find(m, IDENTITY)
    entries = {e["b"] for e in m["edges"] if by_id(m)[e["a"]]["type"] in ("actor", "app") and by_id(m)[e["b"]]["type"] not in ("datastore",)}
    if not entries: return None
    if not ids: return "no identity part"
    gov = {e["b"] for e in m["edges"] if e["a"] in {p["id"] for p in ids}}
    bad = [by_id(m)[i]["label"] for i in entries if i not in gov]
    return True if not bad else f"not governed by identity: {', '.join(bad[:3])}"

def _r_sandbox(m):
    if not find(m, CODING): return None
    sb = find(m, SANDBOX)
    if not sb: return "no sandbox"
    leaks = [p["label"] for p in sb for e in outs(m, p["id"]) if by_id(m)[e["b"]] in cloud_parts(m)]
    return True if not leaks else "the sandbox reaches the cloud directly"

def _r_secrets(m):
    if not (find(m, "", ("agent",)) or cloud_parts(m)): return None
    return True if find(m, r"secret|vault|\bkms\b|key management|key vault|credential") else "no secrets manager"

def _r_tools_governed(m):
    agents = find(m, "", ("agent",))
    if not agents: return None
    reg = find(m, r"registr|\bmcp\b|tool|skill store|catalog")
    if not reg: return "agents have no tool registry"
    idp = {p["id"] for p in find(m, IDENTITY)}
    governed = any(e["a"] in idp for r in reg for e in ins(m, r["id"]))
    return True if governed else "the tool registry isn't governed by identity/policy"

def _r_egress(m):
    cl = cloud_parts(m)
    if not cl or not onprem(m): return None
    return True if find(m, r"dlp|data loss|egress|redact|\bpii\b|guardrail|content filter|masking|classification") else "nothing checks what leaves for the cloud"

def _r_guardrails(m):
    if not find(m, "", ("agent",)): return None
    return True if find(m, r"guardrail|content safety|prompt shield|moderation|output filter|injection|llm guard|nemo guardrails") else "no prompt/output guardrails"

def _r_audit(m):
    if not (find(m, "", ("agent",)) or find(m, "", ("model", "external"))): return None
    return True if find(m, r"audit|siem|immutable log|log store|compliance log") else "no audit log"

def _r_eval_gate(m):
    sk = find(m, r"self.?evolv|skill|fine.?tun|training|\brl\b")
    reg = find(m, r"registr|skill store|model store|catalog")
    if not sk or not reg: return None
    ev = {p["id"] for p in find(m, r"\beval|evaluation|benchmark|test")}
    gated = any(e["a"] in ev and (e["kind"] == "control" or re.search(r"approv|gate|promot|certif", e["verb"].lower())) for r in reg for e in ins(m, r["id"]))
    direct = any(e["b"] in {r["id"] for r in reg} for s in sk for e in outs(m, s["id"]) if s["id"] not in ev)
    return True if gated and not direct else "new skills reach the registry without an evaluation gate"

def _r_human_review(m):
    if not find(m, CODING): return None
    return True if find(m, r"\bgit\b|github|gitlab|repo|pull request|\bpr\b|code review|ci/cd|\bci\b|pipeline") else "the coding agent's changes have no review/CI path"

def _r_ingestion(m):
    ks = find(m, r"vector|knowledge|retriev|\brag\b", ("datastore",))
    if not ks: return None
    ing = {p["id"] for p in find(m, r"ingest|connector|etl|pipeline|indexer|crawl|embedd")}
    fed = any(e["a"] in ing for k in ks for e in ins(m, k["id"]))
    return True if fed else "nothing feeds the knowledge store"

def _r_fallback(m):
    gws = find(m, GATEWAY, ("gateway",))
    models = {p["id"] for p in find(m, "", ("model", "external"))}
    if not gws or not models: return None
    best = max(len([e for e in outs(m, g["id"]) if e["b"] in models]) for g in gws)
    return True if best >= 2 or any(re.search(r"fallback|failover", _t(g)) for g in gws) else "the router has a single model and no fallback"

def _r_async(m):
    if not find(m, "", ("agent",)): return None
    return True if find(m, r"queue|kafka|\bsqs\b|pub/?sub|workflow|temporal|celery|job") else "long agent jobs have no queue or workflow engine"

def _r_orchestrated(m):
    serving = find(m, "", ("model",))
    if not serving: return None
    ctl = {p["id"] for p in find(m, r"control plane|orchestrat|kubernetes|scheduler|slurm|ray")}
    infra = {p["id"] for p in find(m, "", ("infra",))}
    ok = all(any(e["a"] in ctl for e in ins(m, s["id"], "control")) or any(e["b"] in infra and any(x["a"] in ctl for x in ins(m, e["b"], "control")) for e in outs(m, s["id"]))
             for s in serving)
    return True if ok else "model serving isn't managed by the control plane"

def _r_traced(m):
    gws = find(m, GATEWAY, ("gateway",)); obs = {p["id"] for p in find(m, OBS)}
    if not gws: return None
    if not obs: return "no observability"
    return True if all(any(e["b"] in obs for e in outs(m, g["id"])) for g in gws) else "model calls through the router aren't traced"

def _r_agent_traced(m):
    ag = find(m, "", ("agent",)); obs = {p["id"] for p in find(m, OBS)}
    if not ag: return None
    return True if obs and all(any(e["b"] in obs for e in outs(m, a["id"])) for a in ag) else "agent runs aren't traced"

def _r_metered(m):
    gws = find(m, GATEWAY, ("gateway",))
    if not gws: return None
    if find(m, r"cost|finops|budget|meter|billing|quota|chargeback"): return True
    return True if any(re.search(r"token|cost|usage|spend", e["verb"].lower()) for g in gws for e in outs(m, g["id"])) else "model usage isn't metered"


RULES = [
    ("C1", "correctness", 2, "Stores answer, they don't call", "A data store is read and written by others; an arrow starting at a store usually means the direction is backwards.", "Draw the arrow from the part that queries or writes the store.", C4, _r_store_calls),
    ("C2", "correctness", 2, "People start interactions", "People and outside systems call the platform; arrows into them should be responses or notifications.", "Reverse the arrow, or label it as a notification.", C4, _r_actor_target),
    ("C3", "correctness", 1, "Infrastructure hosts, it doesn't send data", "GPU clusters and networks run things; data flows between the services on them.", "Draw '<service> -> <infra>: runs on' instead.", C4, _r_infra_calls),
    ("C4", "correctness", 1, "Control comes from something that controls", "Stores, people, cloud APIs and models don't deploy or govern other parts.", "Make it a data arrow, or start it at the control plane or policy service.", C4, _r_control_from),
    ("C5", "correctness", 2, "Every relationship says what flows", "An unlabelled arrow can't be reviewed or threat-modelled.", "Add ': verb' to each connection.", C4, _r_labels),
    ("C6", "correctness", 1, "Cross-zone hops name a protocol", "Calls that leave a zone are where security and latency are decided.", "Add '(protocol)' to connections between zones.", C4, _r_cross_zone_protocol),
    ("C7", "correctness", 2, "Nothing floats", "A part with no connections is either missing its relationships or doesn't belong.", "Connect it or remove it.", C4, _r_connected),
    ("C8", "clarity", 1, "Everything has a place to run", "Where a part runs decides its trust boundary, cost and latency.", "Put each part under a [zone].", C4, _r_zones),
    ("C9", "clarity", 1, "Readable at a glance", "Past ~20 parts, or one part wired to everything, the diagram stops explaining.", "Split the hub, or draw a second, more detailed map.", C4, _r_size),
    ("S1", "security", 3, "Every entry point is authenticated", "Zero trust: no request reaches an agent or model without identity and policy deciding first.", "Add an identity/policy part with control arrows to each entry point.", ZT, _r_entry_auth),
    ("S2", "security", 3, "Generated code runs in a sandbox", "An agent that writes and runs code can be steered by injected text; isolation contains the damage.", "Add a sandbox (gVisor, Firecracker, E2B) the agent runs code in, with no direct route to the cloud.", f"{OWASP_AGENT}; {OWASP_LLM} LLM05 Improper Output Handling", _r_sandbox),
    ("S3", "security", 2, "Secrets come from a secrets manager", "API keys for cloud models and tools must not live in agent configs or prompts.", "Add a secrets manager (Vault, AWS Secrets Manager, Azure Key Vault).", WAF, _r_secrets),
    ("S4", "security", 2, "Agents only use approved, governed tools", "Excessive agency: an agent's tools and permissions should be the minimum, granted by policy.", "Route tool access through a registry governed by identity/policy.", f"{OWASP_LLM} LLM06 Excessive Agency", _r_tools_governed),
    ("S5", "data", 3, "Data leaving for the cloud is checked", "Private data reaching a cloud model is the main risk of a hybrid platform.", "Add a DLP/redaction step (or guardrail) on the path from the router to cloud models.", f"{OWASP_LLM} LLM02 Sensitive Information Disclosure; {ZT}", _r_egress),
    ("S6", "security", 2, "Prompts and outputs pass guardrails", "Prompt injection and unsafe output are the top LLM risks.", "Add input/output guardrails (e.g. NeMo Guardrails, Llama Guard, content safety) around agent calls.", f"{OWASP_LLM} LLM01 Prompt Injection, LLM05", _r_guardrails),
    ("G1", "governance", 2, "There is an audit trail", "Who asked what, which model answered, and what the agent did must be reconstructable.", "Add an audit log (or SIEM) fed by the router and the agents.", f"{NIST_RMF} Govern", _r_audit),
    ("G2", "governance", 3, "New skills pass an evaluation gate", "Self-improving systems need a measured gate before a change is used.", "Send candidate skills to evaluation, and let evaluation approve them into the registry.", f"{NIST_RMF} Measure/Manage", _r_eval_gate),
    ("G3", "governance", 3, "Agent changes go through review", "Human oversight: code an agent writes reaches production through a pull request, CI and approval.", "Add the code repository / CI pipeline the agent opens changes in.", f"{NIST_RMF} Manage; {OWASP_AGENT}", _r_human_review),
    ("G4", "governance", 1, "Knowledge has a way in", "A retrieval store is only as good and as governed as what is ingested into it.", "Add an ingestion pipeline (connectors, chunking, embeddings) feeding the store.", WAF, _r_ingestion),
    ("R1", "reliability", 2, "The router can fail over", "Model providers rate-limit and fail; a router with one target is a single point of failure.", "Route to at least two models, or name the fallback.", WAF, _r_fallback),
    ("R2", "reliability", 1, "Long agent jobs are queued", "Agent tasks run for minutes; direct calls time out and lose work.", "Add a queue or workflow engine between callers and agents.", WAF, _r_async),
    ("R3", "reliability", 1, "Model serving is orchestrated", "Self-hosted models need health checks, scaling and placement from the control plane.", "Add a control arrow from the control plane to the serving layer or its GPUs.", WAF, _r_orchestrated),
    ("O1", "observability", 2, "Every model call is traced", "The router sees every call; tracing there gives latency, errors and cost in one place.", "Add 'Router -> Observability: traces, tokens'.", f"{WAF}; {NIST_RMF} Measure", _r_traced),
    ("O2", "observability", 1, "Agent runs are traced", "Multi-step agent runs can only be debugged and evaluated with traces.", "Add 'Agent -> Observability: traces'.", f"{NIST_RMF} Measure", _r_agent_traced),
    ("O3", "observability", 2, "Model usage is metered", "Hybrid routing is mostly a cost decision; it needs per-team token and cost metering.", "Label the router's telemetry with tokens/cost, or add a cost/metering part.", WAF, _r_metered),
]
RULE_IDS = {r[0] for r in RULES}


# ---------- fidelity to the brief ----------
_STOP = {"a", "an", "the", "and", "or", "of", "for", "with", "to", "in", "on", "that", "will", "be", "all", "via", "its"}


def _norm_words(t): return {re.sub(r"(ies|es|s)$", "", w) for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if w not in _STOP and len(w) > 1}


def brief_components(project):
    """The components a project's name and goal list ("... will include a, b, and c" / "X with a, b and c")."""
    out = []
    for text in (project.get("goal") or "", project.get("name") or ""):
        mt = None
        for rx in (r"\binclud\w*\s+(.+)", r"\bconsists? of\s+(.+)", r"\bcomponents?(?: are)?:\s*(.+)", r"\bwith\s+(.+)"):
            mt = re.search(rx, text, re.I)
            if mt: break
        if not mt: continue
        for bit in re.split(r",|\band\b", mt.group(1).split(".")[0]):
            bit = re.sub(r"^\s*(a|an|the)\s+", "", bit.strip(), flags=re.I).strip()
            if 2 < len(bit) < 60 and _norm_words(bit) not in [_norm_words(o) for o in out]: out.append(bit)
    return out[:12]


def present(component, m):
    want = _norm_words(component)
    return bool(want) and any(want <= _norm_words(p["label"] + " " + " ".join(p["terms"])) or len(want & _norm_words(p["label"])) >= max(1, round(len(want) * 0.6))
                              for p in m["parts"])


# ---------- the score ----------
def score(m, project=None, overlay=None, review=None):
    """{"total", "parts": {dimension: 0-100}, "rules": [...], "waived": [...], "missing": [...], "brief": [...], "review": ...}."""
    waivers = m.get("waivers") or {}; results = []
    for rid, area, w, title, why, fix, ref, fn in RULES:
        try: r = fn(m)
        except Exception: r = None
        if r is None: continue
        results.append({"id": rid, "area": area, "weight": w, "title": title, "why": why, "fix": fix, "ref": ref,
                        "ok": r is True or rid in waivers, "waived": waivers.get(rid) if r is not True and rid in waivers else None, "detail": "" if r is True else r})
    if review:                                   # the reviewer's fixed-rubric answers, as partial credit
        n = max(1, len(m["edges"]))
        for rid, key, w, title, why in (("J1", "implausible", 3, "Connections make sense", "Each arrow's direction and meaning are plausible to a reviewer."),
                                        ("J2", "bad_protocols", 1, "Protocols fit the hop", "Each named protocol is plausible for that connection.")):
            bad = review.get(key) or []
            results.append({"id": rid, "area": "correctness", "weight": w, "title": title, "why": why, "fix": "See the reviewer's notes below.", "ref": "Reviewer model",
                            "ok": not bad, "credit": max(0.0, 1 - len(bad) / n * 3), "waived": None, "detail": "; ".join(f"{b.get('from')} → {b.get('to')}: {b.get('why')}" for b in bad[:4])})
    def dim(areas):
        rs = [r for r in results if r["area"] in areas]
        tot = sum(r["weight"] for r in rs)
        return None if not tot else 100 * sum(r["weight"] * (1 if r["ok"] else r.get("credit", 0)) for r in rs) / tot
    parts = {"correctness": dim({"correctness", "clarity"}), "practice": dim({"security", "data", "governance", "reliability", "observability"})}
    missing = patterns.missing(m); pat = patterns.PATTERNS.get(m.get("pattern") or "")
    if pat:
        roles = len(pat["roles"]) + sum(1 for rx, _ in pat["if"] if any(re.search(rx, _t(x)) for x in m["parts"]))
        parts["completeness"] = 100 * (roles - len(missing)) / max(1, roles)
    brief = [{"component": c, "present": present(c, m)} for c in brief_components(project or {})]
    cons = (review or {}).get("constraints") or []
    if brief or cons:
        got = sum(1 for b in brief if b["present"]) * 2 + sum(1 for c in cons if c.get("met")); out_of = len(brief) * 2 + len(cons)
        parts["fidelity"] = 100 * got / out_of
    if overlay is not None and m["parts"]:
        matched = sum(1 for p in m["parts"] if overlay.get(p["id"], {}).get("development_count"))
        parts["evidence"] = 100 * min(1.0, matched / len(m["parts"]) / 0.7)
    have = {k: v for k, v in parts.items() if v is not None}
    total = sum(WEIGHTS[k] * v for k, v in have.items()) / max(1, sum(WEIGHTS[k] for k in have))
    return {"total": round(total), "parts": {k: round(v) for k, v in have.items()}, "rules": results, "missing": [{"name": n, "why": w} for n, w in missing],
            "brief": brief, "constraints": cons, "review": review, "waived": [{"id": r["id"], "title": r["title"], "reason": r["waived"]} for r in results if r["waived"]]}


def failing(sc): return [r for r in sc["rules"] if not r["ok"]]
