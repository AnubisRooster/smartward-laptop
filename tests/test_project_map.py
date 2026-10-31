import json, time, unittest
from unittest import mock
from sw import db, maps
from tests import helpers as h
from tests.test_implications import dev, project, reply, hyp
from tests.test_memo import answer

c = h.client
NOW = time.time()
TEXT = """Serving layer: vllm, continuous batching
Scheduler: chunked prefill, scheduler
KV cache: kv cache, prefix caching

Serving layer -> Scheduler
Scheduler -> KV cache
"""


class Parsing(unittest.TestCase):
    def test_lines_become_parts_and_connections(self):
        comps, edges, problems = maps.parse(TEXT)
        self.assertEqual([c["label"] for c in comps], ["Serving layer", "Scheduler", "KV cache"]); self.assertEqual(comps[2]["terms"], ["kv cache", "prefix caching"])
        self.assertEqual(edges, [("c1", "c2"), ("c2", "c3")]); self.assertEqual(problems, [])
        self.assertEqual(maps.parse(maps.to_lines(comps, edges))[:2], (comps, edges))

    def test_problems_are_listed_with_their_line(self):
        _, edges, problems = maps.parse("A: x\nA: y\nA -> Nowhere\n: z")
        self.assertEqual(edges, []); self.assertEqual(len(problems), 3); self.assertIn("Line 2", problems[0])

    def test_nothing_in_a_label_can_become_diagram_markup(self):
        comps, _, _ = maps.parse('Evil"]; x[<img src=x onerror=alert(1)>]: x\nclick c1 href "javascript:alert(1)": y\nB{{x}}|y|`z`: q')
        for c_ in comps: self.assertRegex(c_["label"], r"^[\w .+/&()-]{1,40}$")
        import re
        for line in maps.mermaid(comps, [], {}).splitlines()[1:]: self.assertRegex(line, r'^  c\d+\["[\w .+/&()·-]+"\]$')      # one quoted node per line, nothing else

class Overlay(unittest.TestCase):
    def setUp(self):
        h.reset(); self.src = h.add_source("Lab blog"); self.pid = project()
        a = h.add_article(self.src, "Story", "x" * 600)
        self.d1 = dev(a, claim="Chunked prefill raises throughput under the scheduler.")
        self.d2 = dev(a, claim="Prefix caching saves memory in the KV cache.", evidence="claimed")
        secret = h.add_article(self.src, "Mine", "x" * 600, private=1); dev(secret, claim="Secret prefix caching trick.")

    def test_items_land_on_the_parts_whose_words_they_use_and_threats_colour_first(self):
        db.x("INSERT INTO hypotheses(project_id,headline,implication,direction,confidence,status,created,updated) VALUES(?,?,?,?,?,?,?,?)",
             (self.pid, "Prefix caching may undercut the cache design", "If the KV cache keeps shrinking...", "threatens", "low", "new", NOW, NOW))
        comps, edges, _ = maps.parse(TEXT); o = maps.overlay(self.pid, comps, NOW)
        self.assertEqual(o["c2"]["development_count"], 1); self.assertEqual(o["c2"]["tone"], "news"); self.assertEqual(o["c2"]["measured"], 1)
        self.assertEqual(o["c3"]["development_count"], 1); self.assertEqual(o["c3"]["tone"], "threatens")      # the private trick is not counted
        self.assertEqual(o["c1"]["development_count"], 2)                                                     # both name vLLM in their subject
        src = maps.mermaid(comps, edges, o); self.assertIn('c3["KV cache · 2"]', src); self.assertIn("class c3 threatens", src); self.assertIn("c1 --> c2", src)

    def test_save_view_preview_and_phone_reads_it(self):
        self.assertIsNone(c.get(f"/api/projects/{self.pid}/map").json()["map"])
        self.assertEqual(c.put(f"/api/projects/{self.pid}/map", json={"text": "A: x\nA -> B"}).status_code, 400)
        m = c.put(f"/api/projects/{self.pid}/map", json={"text": TEXT}).json()["map"]; self.assertIn("flowchart LR", m["mermaid"])
        p = c.post(f"/api/projects/{self.pid}/map/preview", json={"text": "A: x\nA -> B"}).json(); self.assertEqual(len(p["problems"]), 1)
        self.assertEqual(c.put("/api/projects/999/map", json={"text": TEXT}).status_code, 404)
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get(f"/api/projects/{self.pid}/map", headers=VIA).status_code, 200)
        self.assertEqual(c.put(f"/api/projects/{self.pid}/map", json={"text": TEXT}, headers=VIA).status_code, 403)
        self.assertEqual(c.post(f"/api/projects/{self.pid}/map/draft", headers=VIA).status_code, 403)
        c.delete(f"/api/projects/{self.pid}"); self.assertEqual(db.q("SELECT COUNT(*) n FROM project_maps", one=True)["n"], 0)

    def test_a_draft_is_cleaned_and_not_saved_and_private_repos_stay_local(self):
        db.set_setting("api_key", "sk-test"); db.set_setting("model", "openrouter/openrouter/free")
        out = {"parts": [{"name": "Serving", "terms": ["vllm"]}, {"name": "Cache<script>", "terms": ["kv cache"]}, "junk"], "connections": [["Serving", "Cache<script>"], ["Serving", "Ghost"]]}
        with mock.patch("sw.llm.time.sleep"), mock.patch("litellm.completion", return_value=answer(out)) as comp: d = c.post(f"/api/projects/{self.pid}/map/draft").json()
        self.assertEqual(d["text"], "Serving: vllm\nCachescript: kv cache\n\nServing -> Cachescript\n"); self.assertIsNone(maps.get(self.pid))
        self.assertTrue(comp.call_args.kwargs["model"].startswith("openrouter/"))
        db.x("INSERT INTO project_links(project_id,kind,url,private) VALUES(?,?,?,1)", (self.pid, "github", "https://github.com/me/secret"))
        with mock.patch("sw.llm.time.sleep"), mock.patch("litellm.completion", return_value=answer(out)) as comp: c.post(f"/api/projects/{self.pid}/map/draft")
        self.assertTrue(comp.call_args.kwargs["model"].startswith("ollama"))

    def test_the_project_share_lists_where_things_land_on_the_stack(self):
        from sw import share
        maps.save(self.pid, TEXT)
        out = share.render("project", self.pid, "markdown")["content"]
        self.assertIn("## Where it lands on the stack", out); self.assertIn("**KV cache**: 1 recent development (0 measured)", out); self.assertNotIn("**Serving layer**: 0", out)

    def test_maps_travel_with_a_backup(self): self.assertIn("project_maps", h.api.TABLES)


if __name__ == "__main__":
    unittest.main()
