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


def as_json(text):
    """A map's lines in the drafting JSON shape, as a model would send them."""
    m = maps.parse(text); names = {p["id"]: p["label"] for p in m["parts"]}
    return {"pattern": m["pattern"], "zones": m["zones"],
            "parts": [{"name": p["label"], "type": p["type"], "zone": p["zone"], "terms": p["terms"], "suggested": p["suggested"], "why": p["note"]} for p in m["parts"]],
            "connections": [{"from": names[e["a"]], "to": names[e["b"]], "verb": e["verb"], "protocol": e["protocol"], "kind": e["kind"]} for e in m["edges"]]}


class Drafting(unittest.TestCase):
    def setUp(self):
        from tests.test_rules import GOOD
        h.reset(); db.set_setting("api_key", "sk-test"); db.set_setting("model", "openrouter/anthropic/claude-sonnet-4-5"); db.set_setting("cloud_scope", "analysis")
        db.set_setting("design_model", ""); db.set_setting("analysis_model", "openrouter/judge:free"); db.set_setting("analysis_fallbacks", [])
        self.pid = project(name="AI platform", goal="An enterprise AI platform that will include a coding agent, harness and model router.")
        self.good = as_json(GOOD)
        weak = GOOD
        for line in ("Secrets (service): vault\n", "Audit log (datastore): audit, siem\n", "Job queue (service): temporal, queue\n"): weak = weak.replace(line, "")
        weak = "\n".join(l for l in weak.splitlines() if not any(x in l for x in ("Secrets", "Audit log", "Job queue"))) + "\nDevelopers -> Coding agent: asks\n"
        self.weak = as_json(weak)
        poor = {**self.weak, "parts": self.weak["parts"][:6], "connections": []}
        self.poor = poor
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()

    def run_draft(self):
        """Start a draft with background work run inline, then take the finished result the way the page does."""
        with mock.patch.object(h.api, "bg", lambda fn, *a: fn(*a)): self.assertTrue(c.post(f"/api/projects/{self.pid}/map/draft").json()["started"])
        st = c.get(f"/api/projects/{self.pid}/map/draft/status", params={"take": True}).json()
        self.assertFalse(st["running"]); self.assertIsNone(st["error"], st["error"])
        self.assertIsNone(c.get(f"/api/projects/{self.pid}/map/draft/status").json()["result"])          # handed over once
        return st["result"]

    def fake(self, drafts, repair=None, review=None):
        calls = {"draft": [], "review": [], "repair": []}; it = iter(drafts)
        def f(**kw):
            msg = kw["messages"][0]["content"]
            kind = "review" if msg.startswith("You review") else "repair" if "A review scored it" in msg else "draft"
            calls[kind].append(kw)
            if kind == "review": return answer(review or {"implausible": [], "bad_protocols": [], "constraints": [{"text": "has a coding agent", "met": True}]})
            if kind == "repair": return answer(repair or self.good)
            return answer(next(it))
        return f, calls

    def test_three_drafts_are_scored_the_best_is_reviewed_by_another_model_and_repaired(self):
        f, calls = self.fake([self.poor, self.weak, self.poor])
        with mock.patch("litellm.completion", side_effect=f): d = self.run_draft()
        self.assertEqual(len(calls["draft"]), 3); self.assertEqual({k["model"] for k in calls["draft"]}, {"openrouter/anthropic/claude-sonnet-4-5"})
        self.assertEqual({k["model"] for k in calls["review"]}, {"openrouter/judge:free"})                                      # never the drafter
        self.assertEqual(d["history"][0]["step"], "drafts"); self.assertEqual(len(d["history"][0]["scores"]), 3)
        rep = calls["repair"][0]["messages"][0]["content"]; self.assertIn("S3 Secrets come from a secrets manager", rep); self.assertIn("G1", rep)
        self.assertEqual(d["score"]["parts"]["practice"], 100); self.assertEqual(d["score"]["parts"]["evidence"], 0)      # an empty test library: no evidence
        self.assertTrue(any(h_["step"] == "repair" for h_ in d["history"])); self.assertIsNone(maps.get(self.pid))
        p = calls["draft"][0]["messages"][0]["content"]; self.assertIn("OWASP LLM Top 10", p); self.assertIn("S2 Generated code runs in a sandbox", p)
        saved = c.put(f"/api/projects/{self.pid}/map", json={"text": d["text"]}).json()["map"]
        self.assertTrue(saved["reviewed"]); self.assertEqual(saved["score"]["total"], d["score"]["total"])                                       # the review travels with the saved lines

    def test_a_repair_that_renames_your_parts_or_scores_lower_is_not_used(self):
        renamed = as_json(maps.to_text(from_good := maps.parse(__import__("tests.test_rules", fromlist=["GOOD"]).GOOD)).replace("Model router", "LLM gateway"))
        f, calls = self.fake([self.weak, self.weak, self.weak], repair=renamed)
        with mock.patch("litellm.completion", side_effect=f): d = self.run_draft()
        self.assertIn("Model router (gateway)", d["text"]); self.assertEqual(d["history"][-1]["step"], "repair rejected")
        f, calls = self.fake([self.weak, self.weak, self.weak], repair=self.poor)
        with mock.patch("litellm.completion", side_effect=f): d2 = self.run_draft()
        self.assertEqual(d2["history"][-1]["step"], "repair rejected"); self.assertGreater(len(maps.parse(d2["text"])["parts"]), 6)

    def test_one_failed_draft_is_fine_and_a_busy_reviewer_doesnt_stop_the_draft(self):
        it = iter([self.good, RuntimeError("bad json reply"), self.weak])
        def f(**kw):
            msg = kw["messages"][0]["content"]
            if msg.startswith("You review"): raise RuntimeError("429 rate limit")
            x = next(it, self.good)
            if isinstance(x, Exception): return NS(choices=[NS(message=NS(content="not json"))], usage=NS(prompt_tokens=1, completion_tokens=1))
            return answer(x)
        from types import SimpleNamespace as NS
        with mock.patch("litellm.completion", side_effect=f): d = self.run_draft()
        self.assertEqual(len(d["history"][0]["scores"]), 2); self.assertIsNone(d["reviewer"])

    def test_review_on_demand_is_stored_with_the_lines_and_goes_stale_when_they_change(self):
        from tests.test_rules import GOOD
        f, calls = self.fake([], review={"implausible": [{"from": "Coding agent", "to": "Harness", "why": "odd"}], "bad_protocols": [], "constraints": []})
        with mock.patch("litellm.completion", side_effect=f): r = c.post(f"/api/projects/{self.pid}/map/review", json={"text": GOOD}).json()
        self.assertTrue(r["reviewed"]); self.assertFalse(next(x for x in r["score"]["rules"] if x["id"] == "J1")["ok"])
        self.assertTrue(c.post(f"/api/projects/{self.pid}/map/preview", json={"text": GOOD + "\n# a comment\n"}).json()["reviewed"])      # same map, same review
        self.assertFalse(c.post(f"/api/projects/{self.pid}/map/preview", json={"text": GOOD + "Coding agent -> GPUs: runs on\n"}).json()["reviewed"])
        self.assertEqual(c.post(f"/api/projects/{self.pid}/map/review", json={"text": "A: x\nA -> B"}).status_code, 400)
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in(); self.assertEqual(c.post(f"/api/projects/{self.pid}/map/review", json={"text": GOOD}, headers=VIA).status_code, 403)

    def test_private_projects_draft_and_review_locally(self):
        db.x("INSERT INTO project_links(project_id,kind,url,private) VALUES(?,?,?,1)", (self.pid, "github", "https://github.com/me/secret"))
        f, calls = self.fake([self.good] * 3)
        with mock.patch("litellm.completion", side_effect=f): self.run_draft()
        self.assertTrue(all(k["model"].startswith("ollama") for k in calls["draft"] + calls["review"]))

    def test_a_chosen_design_model_drafts(self):
        db.set_setting("design_model", "openrouter/some/strong-model")
        f, calls = self.fake([self.good] * 3)
        with mock.patch("litellm.completion", side_effect=f): d = self.run_draft()
        self.assertEqual({k["model"] for k in calls["draft"]}, {"openrouter/some/strong-model"}); self.assertEqual(d["model"], "openrouter/some/strong-model")

    def test_progress_is_reported_and_a_second_start_is_refused_while_running(self):
        from sw import maps as mp
        mp.JOBS[self.pid] = {"running": True, "step": "Drafting 3 versions (1 of 3 back)", "started": time.time() - 65, "result": None, "error": None}
        st = c.get(f"/api/projects/{self.pid}/map/draft/status").json(); self.assertEqual(st["step"], "Drafting 3 versions (1 of 3 back)"); self.assertGreaterEqual(st["elapsed"], 65)
        self.assertEqual(c.post(f"/api/projects/{self.pid}/map/draft").status_code, 409); mp.JOBS.pop(self.pid)
        self.assertEqual(c.post("/api/projects/999/map/draft").status_code, 404)

    def test_a_failed_draft_reports_its_error(self):
        with mock.patch("litellm.completion", side_effect=RuntimeError("401 bad key")), mock.patch.object(h.api, "bg", lambda fn, *a: fn(*a)):
            c.post(f"/api/projects/{self.pid}/map/draft")
        st = c.get(f"/api/projects/{self.pid}/map/draft/status", params={"take": True}).json(); self.assertIn("401", st["error"]); self.assertIsNone(st["result"])

    def test_maps_and_reviews_travel_with_a_backup(self): self.assertIn("project_maps", h.api.TABLES); self.assertIn("map_reviews", h.api.TABLES)


if __name__ == "__main__":
    unittest.main()
