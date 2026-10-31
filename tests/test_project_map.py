import time, unittest
from unittest import mock
from sw import db, maps, patterns
from tests import helpers as h
from tests.test_implications import dev, project
from tests.test_memo import answer

c = h.client
NOW = time.time()
TEXT = """@pattern llm_serving
Users (actor): developers
API gateway (gateway): api gateway
Scheduler (service): chunked prefill, scheduler
Metrics (service): prometheus, tracing

[On-prem data center]
vLLM server (model): vllm
KV cache (datastore): kv cache, prefix caching
GPUs (infra): gpu

Users -> API gateway: send prompts (OpenAI API)
API gateway -> Scheduler: queues requests
Scheduler -> vLLM server: batches
vLLM server -> KV cache: reads and writes
vLLM server => GPUs: runs on
vLLM server -> Metrics: exports metrics
"""


class Parsing(unittest.TestCase):
    def test_parts_zones_types_and_labelled_connections(self):
        m = maps.parse(TEXT)
        self.assertEqual(m["problems"], []); self.assertEqual(m["pattern"], "llm_serving"); self.assertEqual(m["zones"], ["On-prem data center"])
        p = {x["label"]: x for x in m["parts"]}
        self.assertEqual((p["KV cache"]["type"], p["KV cache"]["zone"], p["KV cache"]["terms"]), ("datastore", "On-prem data center", ["kv cache", "prefix caching"]))
        self.assertEqual(p["Users"]["zone"], "")
        self.assertEqual(m["edges"][0], {"a": "c1", "b": "c2", "verb": "send prompts", "protocol": "OpenAI API", "kind": "data"}); self.assertEqual(m["edges"][-2]["kind"], "control")
        self.assertEqual(maps.parse(maps.to_text(m))["parts"], m["parts"])

    def test_the_old_plain_format_still_works(self):
        m = maps.parse("Serving layer: vllm, continuous batching\nKV cache: kv cache\n\nServing layer -> KV cache\n")
        self.assertEqual([(x["label"], x["type"]) for x in m["parts"]], [("Serving layer", "service"), ("KV cache", "service")]); self.assertEqual(m["edges"][0]["verb"], "")

    def test_suggested_parts_notes_slashes_and_problems(self):
        m = maps.parse("~Sandbox (service): sandbox, docker/kubernetes, ci/cd  # the agent runs code\nA (widget): x\nSandbox -> Nowhere\n@pattern nonsense")
        s = m["parts"][0]
        self.assertTrue(s["suggested"]); self.assertEqual(s["note"], "the agent runs code"); self.assertEqual(s["terms"], ["sandbox", "docker", "kubernetes", "ci/cd"])
        self.assertEqual(len(m["problems"]), 3); self.assertIn("unknown type", m["problems"][0]); self.assertIn("unknown pattern", m["problems"][1]); self.assertIn("isn't listed", m["problems"][2])

    def test_nothing_in_the_text_can_become_diagram_markup(self):
        m = maps.parse('Evil"]; x[<img src=x onerror=alert(1)>] (service): x\n[Zone"]; click z1 call alert(1)]\nB{{x}}|y|`z` (agent): q\n'
                       'Evil x img srcx onerroralert1 -> Bxyz: <b>hi</b>|"x"')
        safe = r"[\w .,:+/&'·-]*"
        for line in maps.mermaid(m, {}).splitlines()[1:]:
            self.assertRegex(line.strip(), r'^(c\d+[\[\(\{>/]+"' + safe + r'"[\]\)\}/\\]+|subgraph z\d+\["' + safe + r'"\]|direction TB|end|style z\d+ [\w:#,. -]+|c\d+ -\.?-?->(\|"' + safe + r'"\|)? c\d+|classDef \w+ [\w:#,-]+( [\w:#,-]+)?|class [c\d,]+ \w+)$')

    def test_plural_hyphen_and_case_insensitive_matching(self):
        rx = maps.term_rx(["coding agent", "self-evolving skill", "run:ai"])
        for t in ("Coding Agents ship", "self evolving skills", "Self-Evolving skill", "NVIDIA Run:ai is open"): self.assertTrue(rx.search(t), t)
        for t in ("codingagentic", "agent coding"): self.assertFalse(rx.search(t), t)


class Checking(unittest.TestCase):
    def test_a_complete_serving_map_has_no_warnings(self):
        self.assertEqual([x for x in patterns.check(maps.parse(TEXT)) if x["level"] == "warn"], [])

    def test_missing_roles_loose_parts_and_cloud_calls_around_the_router_are_reported(self):
        m = maps.parse("@pattern agent_platform\nCoding agent (agent): claude code\nModel router (gateway): routellm\n[AWS]\nBedrock (external): bedrock\n[]\nLonely (service): x\n"
                       "Coding agent -> Bedrock\nCoding agent -> Model router: sends prompts\nModel router -> Bedrock: routes")
        text = " ".join(x["text"] for x in patterns.check(m))
        for want in ("No identity & policy", "No observability", "No sandbox", "“Lonely” isn't connected", "“Coding agent” calls “Bedrock” directly", "1 connection doesn't say"): self.assertIn(want, text)
        self.assertNotIn("No gateway", text)

    def test_the_pattern_is_chosen_from_the_project(self):
        self.assertEqual(patterns.select("AI Platform with coding agent, harness, control plane and self evolving skills"), "agent_platform")
        self.assertEqual(patterns.select("Explore vLLM throughput and KV cache"), "llm_serving"); self.assertIsNone(patterns.select("Gardening notes"))


class Overlay(unittest.TestCase):
    def setUp(self):
        h.reset(); self.src = h.add_source("Lab blog"); self.pid = project()
        a = h.add_article(self.src, "Story", "x" * 600)
        self.d1 = dev(a, claim="Chunked prefill raises throughput under the scheduler.")
        self.d2 = dev(a, claim="Prefix caching saves memory in the KV cache.", evidence="claimed")
        secret = h.add_article(self.src, "Mine", "x" * 600, private=1); dev(secret, claim="Secret prefix caching trick.")

    def test_items_land_on_parts_with_counts_per_word_and_threats_colour_first(self):
        db.x("INSERT INTO hypotheses(project_id,headline,implication,direction,confidence,status,created,updated) VALUES(?,?,?,?,?,?,?,?)",
             (self.pid, "Prefix caching may undercut the cache design", "If the KV cache keeps shrinking...", "threatens", "low", "new", NOW, NOW))
        b = maps.build(self.pid, TEXT); o = {p["label"]: b["overlay"][p["id"]] for p in b["parts"]}
        self.assertEqual(o["KV cache"]["development_count"], 1); self.assertEqual(o["KV cache"]["tone"], "threatens")     # the private trick is not counted
        self.assertEqual(o["KV cache"]["terms"], {"kv cache": 1, "prefix caching": 1}); self.assertEqual(o["GPUs"]["terms"], {"gpu": 0})
        self.assertEqual(o["vLLM server"]["development_count"], 2)                                                      # both name vLLM in their subject
        kv = next(p["id"] for p in b["parts"] if p["label"] == "KV cache")
        self.assertIn(f'{kv}[("KV cache · 2")]', b["mermaid"]); self.assertIn(f"class {kv} threatens", b["mermaid"]); self.assertIn("-.->", b["mermaid"])
        self.assertIn("No recent developments mention: Users", " ".join(x["text"] for x in b["checks"]))

    def test_save_view_preview_and_phone_reads_it(self):
        self.assertIsNone(c.get(f"/api/projects/{self.pid}/map").json()["map"])
        self.assertEqual(c.put(f"/api/projects/{self.pid}/map", json={"text": "A: x\nA -> B"}).status_code, 400)
        m = c.put(f"/api/projects/{self.pid}/map", json={"text": TEXT}).json()["map"]
        self.assertIn("flowchart TB", m["mermaid"]); self.assertEqual(m["pattern_title"], "LLM serving"); self.assertIn("checks", m)
        p = c.post(f"/api/projects/{self.pid}/map/preview", json={"text": "A: x\nA -> B"}).json(); self.assertEqual(len(p["problems"]), 1); self.assertIn("terms", p["overlay"]["c1"])
        self.assertEqual(c.put("/api/projects/999/map", json={"text": TEXT}).status_code, 404)
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get(f"/api/projects/{self.pid}/map", headers=VIA).status_code, 200)
        self.assertEqual(c.put(f"/api/projects/{self.pid}/map", json={"text": TEXT}, headers=VIA).status_code, 403)
        self.assertEqual(c.post(f"/api/projects/{self.pid}/map/draft", headers=VIA).status_code, 403)
        c.delete(f"/api/projects/{self.pid}"); self.assertEqual(db.q("SELECT COUNT(*) n FROM project_maps", one=True)["n"], 0)

    def test_the_project_share_lists_where_things_land(self):
        from sw import share
        maps.save(self.pid, TEXT)
        out = share.render("project", self.pid, "markdown")["content"]
        self.assertIn("## Where it lands on the stack", out); self.assertIn("**KV cache**: 1 recent development (0 measured)", out)


class Drafting(unittest.TestCase):
    def setUp(self):
        h.reset(); db.set_setting("api_key", "sk-test"); db.set_setting("model", "openrouter/anthropic/claude-sonnet-4-5"); db.set_setting("cloud_scope", "analysis")
        db.set_setting("design_model", "")
        self.pid = project(name="AI platform", goal="An enterprise AI platform with a coding agent, harness and model router.")
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()

    FIRST = {"pattern": "agent_platform", "zones": ["On-prem data center", "AWS"], "parts": [
        {"name": "Coding agent", "type": "agent", "terms": ["claude code", "codex"]}, {"name": "Model router", "type": "gateway", "terms": ["routellm"]},
        {"name": "Bedrock", "type": "external", "zone": "AWS", "terms": ["bedrock"]}, {"name": "Cache<script>", "type": "weird", "terms": ["x"]}],
        "connections": [{"from": "Coding agent", "to": "Bedrock", "verb": "calls"}, {"from": "Coding agent", "to": "Ghost"}]}
    SECOND = {"pattern": "agent_platform", "zones": ["On-prem data center", "AWS"], "parts": [
        {"name": "Coding agent", "type": "agent", "terms": ["claude code", "codex"]}, {"name": "Model router", "type": "gateway", "terms": ["routellm"]},
        {"name": "Bedrock", "type": "external", "zone": "AWS", "terms": ["bedrock"]},
        {"name": "Sandbox", "type": "service", "terms": ["sandbox"], "suggested": True, "why": "runs generated code"},
        {"name": "Identity", "type": "service", "terms": ["sso", "rbac"], "suggested": True, "why": "who may use what"},
        {"name": "Observability", "type": "service", "terms": ["tracing", "evals"], "suggested": True, "why": "traces and evals"},
        {"name": "Vector store", "type": "datastore", "terms": ["vector database"], "suggested": True, "why": "company data"},
        {"name": "Skill registry", "type": "service", "terms": ["mcp", "agent skills"], "suggested": True, "why": "approved tools"},
        {"name": "Cache<script>", "type": "datastore", "terms": ["x"]}],
        "connections": [{"from": "Coding agent", "to": "Model router", "verb": "sends prompts", "protocol": "OpenAI API"}, {"from": "Model router", "to": "Bedrock", "verb": "routes"},
                        {"from": "Coding agent", "to": "Sandbox", "verb": "runs code"}, {"from": "Identity", "to": "Model router", "verb": "authorizes", "kind": "control"},
                        {"from": "Coding agent", "to": "Observability", "verb": "sends traces"}, {"from": "Coding agent", "to": "Vector store", "verb": "retrieves"},
                        {"from": "Coding agent", "to": "Skill registry", "verb": "loads skills", "protocol": "MCP"}, {"from": "Coding agent", "to": "Cachescript", "verb": "caches"}]}

    def test_a_draft_uses_the_main_model_is_checked_revised_cleaned_and_not_saved(self):
        tid = db.x("INSERT INTO themes(name,key,type,created) VALUES('Claude Code','claude code','product',?)", (NOW,))
        for i in range(3): db.x("INSERT INTO mentions(article_id,theme_id,ts) VALUES(?,?,?)", (i + 1, tid, NOW))
        calls = []
        def fake(**kw): calls.append(kw); return answer(self.FIRST if len(calls) == 1 else self.SECOND)
        with mock.patch("litellm.completion", side_effect=fake): d = c.post(f"/api/projects/{self.pid}/map/draft").json()
        self.assertEqual(calls[0]["model"], "openrouter/anthropic/claude-sonnet-4-5"); self.assertEqual(len(calls), 2)
        p1 = calls[0]["messages"][0]["content"]; self.assertIn("Enterprise agent platform", p1); self.assertIn("Claude Code", p1)       # the pattern and the library's words
        self.assertIn("calls “Bedrock” directly", calls[1]["messages"][0]["content"])                                                    # the revision is told what was wrong
        self.assertTrue(d["revised"]); self.assertEqual([x for x in d["checks"] if x["level"] == "warn"], []); self.assertIn("~Sandbox (service): sandbox  # runs generated code", d["text"])
        self.assertIsNone(maps.get(self.pid))

    def test_a_revision_that_is_not_better_is_not_used_and_bad_input_is_cleaned(self):
        with mock.patch("litellm.completion", return_value=answer(self.FIRST)): d = c.post(f"/api/projects/{self.pid}/map/draft").json()
        self.assertFalse(d["revised"]); self.assertIn("Cachescript (service): x", d["text"]); self.assertNotIn("Ghost", d["text"]); self.assertIn("[AWS]", d["text"])

    def test_a_busy_main_model_falls_back_to_the_analysis_models_and_private_projects_stay_local(self):
        db.set_setting("analysis_model", "openrouter/a:free"); db.set_setting("analysis_fallbacks", []); seen = []
        def fake(**kw):
            seen.append(kw["model"])
            if kw["model"] == "openrouter/anthropic/claude-sonnet-4-5": raise RuntimeError("429 rate limit")
            return answer(self.SECOND)
        with mock.patch("litellm.completion", side_effect=fake): self.assertEqual(c.post(f"/api/projects/{self.pid}/map/draft").status_code, 200)
        self.assertEqual(seen[:2], ["openrouter/anthropic/claude-sonnet-4-5", "openrouter/a:free"])
        db.x("INSERT INTO project_links(project_id,kind,url,private) VALUES(?,?,?,1)", (self.pid, "github", "https://github.com/me/secret"))
        with mock.patch("litellm.completion", return_value=answer(self.SECOND)) as comp: c.post(f"/api/projects/{self.pid}/map/draft")
        self.assertTrue(comp.call_args.kwargs["model"].startswith("ollama"))

    def test_words_no_article_uses_are_sent_back_for_better_ones(self):
        src = h.add_source("Blog"); a = h.add_article(src, "News", "x" * 600)
        dev(a, claim="Claude Code adds MCP servers, RBAC and SSO; RouteLLM routes prompts to Bedrock; tracing and evals; vector database support; sandbox runs.")
        import copy
        vague = copy.deepcopy(self.SECOND)
        for part in vague["parts"]: part["terms"] = ["central management"]
        calls = []
        def fake(**kw): calls.append(kw); return answer(vague if len(calls) == 1 else self.SECOND)
        with mock.patch("litellm.completion", side_effect=fake): d = c.post(f"/api/projects/{self.pid}/map/draft").json()
        self.assertEqual(len(calls), 2); self.assertIn("WORDS NO ARTICLE USES", calls[1]["messages"][0]["content"]); self.assertTrue(d["revised"]); self.assertIn("claude code", d["text"])

    def test_a_revision_that_renames_your_parts_or_borrows_words_is_not_used(self):
        import copy
        renamed = copy.deepcopy(self.SECOND); renamed["parts"][1]["name"] = "vLLM"                     # "Model router" renamed to chase matches
        for x in renamed["connections"]:
            x["from"] = "vLLM" if x["from"] == "Model router" else x["from"]; x["to"] = "vLLM" if x["to"] == "Model router" else x["to"]
        with mock.patch("litellm.completion", side_effect=[answer(self.FIRST), answer(renamed)]): d = c.post(f"/api/projects/{self.pid}/map/draft").json()
        self.assertFalse(d["revised"]); self.assertIn("Model router (gateway)", d["text"])
        m = maps.parse("A (service): kv cache\nB (service): kv cache, x\nA -> B: y")
        self.assertEqual(maps.shared_words(m), {"kv cache"}); self.assertIn("Used on more than one part", " ".join(x["text"] for x in patterns.check(m)))

    def test_a_chosen_design_model_is_used(self):
        db.set_setting("design_model", "openrouter/some/strong-model")
        with mock.patch("litellm.completion", return_value=answer(self.SECOND)) as comp: d = c.post(f"/api/projects/{self.pid}/map/draft").json()
        self.assertEqual(comp.call_args.kwargs["model"], "openrouter/some/strong-model"); self.assertEqual(d["model"], "openrouter/some/strong-model")

    def test_maps_travel_with_a_backup(self): self.assertIn("project_maps", h.api.TABLES)


if __name__ == "__main__":
    unittest.main()
