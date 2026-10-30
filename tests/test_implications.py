import json, time, unittest
from types import SimpleNamespace as NS
from unittest import mock
from sw import db, implications as im, llm, signals
from tests import helpers as h

c = h.client
NOW = time.time()


def project(name="vLLM Architecture Exploration", goal="Explore architectures for faster inference serving", brief=""):
    return db.x("INSERT INTO projects(name,goal,brief,created,updated) VALUES(?,?,?,?,?)", (name, goal, brief, NOW, NOW))


def dev(article, claim="Chunked prefill raises serving throughput.", evidence="measured", domains=("Inference serving",), grounded=1, days=2, kind="efficiency", value="2.1x"):
    return db.x("INSERT INTO developments(article_id,kind,subject,claim,metric,value,baseline,evidence,domains,quote,grounded,ts,created,model) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (article, kind, "vLLM 0.12", claim, "throughput", value, "vLLM 0.9", evidence, json.dumps(list(domains)), "q", grounded, NOW - days * 86400, NOW, "m"))


def reply(items): return NS(choices=[NS(message=NS(content=json.dumps({"hypotheses": items})))], usage=NS(prompt_tokens=1, completion_tokens=1))


def hyp(evidence, **kw):
    base = {"headline": "Chunked prefill may cut your serving latency", "implication": "Evidence 1 suggests the benchmark should include long prompts. This could change what you measure.", "direction": "accelerates",
            "confidence": "medium", "evidence": evidence, "counter_evidence": [], "what_would_change_my_mind": "A result where prefill chunking slows short prompts.", "suggested_action": "Add a long-prompt case to the benchmark."}
    base.update(kw); return base


class Setup(unittest.TestCase):
    def setUp(self):
        h.reset(); db.set_setting("api_key", "sk-test"); db.set_setting("model", "openrouter/openrouter/free")
        self.src = h.add_source("Lab blog"); self.arts = [h.add_article(self.src, f"Story {i}", "x" * 600) for i in range(6)]
        self.pid = project(); self.ids = [dev(a, claim=f"Claim number {i}.", evidence="measured" if i < 3 else "claimed") for i, a in enumerate(self.arts)]
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()


class Evidence(Setup):
    def test_a_project_is_about_the_domains_whose_words_it_uses(self):
        ds = signals.domains(); names = [d["name"] for d in im.project_domains({"name": "vLLM thing", "goal": "", "brief": ""}, ds)]
        self.assertEqual(names, ["Inference serving"]); self.assertEqual(len(im.project_domains({"name": "Zzz", "goal": "", "brief": ""}, ds)), len(ds))      # no match: every domain

    def test_only_checked_recent_developments_in_the_projects_domains_reach_the_model_strongest_first(self):
        db.x("UPDATE developments SET grounded=0 WHERE id=?", (self.ids[0],))                                                    # unverified: excluded
        dev(self.arts[0], claim="Other domain.", domains=("Frontier models",)); dev(self.arts[1], claim="Too old.", days=90)
        g = im.gather(db.q("SELECT * FROM projects", one=True), NOW)
        claims = [r["claim"] for r in g["evidence"]]; self.assertNotIn("Claim number 0.", claims); self.assertNotIn("Other domain.", claims); self.assertNotIn("Too old.", claims)
        self.assertEqual([r["evidence"] for r in g["evidence"]], ["measured", "measured", "claimed", "claimed", "claimed"]); self.assertTrue(g["trends"])


class Cleaning(Setup):
    def ev(self): return im.gather(db.q("SELECT * FROM projects", one=True), NOW)["evidence"]

    def clean(self, items): return im.clean({"hypotheses": items}, self.ev())

    def test_citing_something_that_was_not_given_drops_the_hypothesis_and_unknown_numbers_are_removed(self):
        out, dropped = self.clean([hyp([99999]), hyp([self.ids[0], 424242]), hyp([]), "junk"])
        self.assertEqual(len(out), 1); self.assertEqual(out[0]["evidence"], [self.ids[0]]); self.assertEqual(dropped, 3)

    def test_confidence_cannot_outrun_the_evidence(self):
        ev = {r["id"]: r for r in self.ev()}; claimed_only = [i for i, r in ev.items() if r["evidence"] == "claimed"][:1]
        self.assertEqual(self.clean([hyp(claimed_only, confidence="high")])[0][0]["confidence"], "low")                          # one claim, one article
        two_measured = [i for i, r in ev.items() if r["evidence"] == "measured"][:2]
        self.assertEqual(self.clean([hyp(two_measured, confidence="high")])[0][0]["confidence"], "high")                         # two measured results from different articles
        self.assertEqual(self.clean([hyp(two_measured[:1], confidence="high")])[0][0]["confidence"], "medium")                   # one measured result

    def test_over_strong_wording_lowers_confidence(self):
        ev = {r["id"]: r for r in self.ev()}; one = [i for i, r in ev.items() if r["evidence"] == "measured"][:1]
        self.assertEqual(self.clean([hyp(one, headline="This will make your benchmark obsolete", confidence="medium")])[0][0]["confidence"], "low")

    def test_odd_fields_are_normalised_and_the_list_is_capped(self):
        out, _ = self.clean([hyp([self.ids[0]], direction="sideways", confidence="certain") for _ in range(7)])
        self.assertEqual((len(out), out[0]["direction"], out[0]["confidence"]), (4, "neutral", "low"))

    def test_counter_evidence_must_be_real_and_not_also_support(self):
        out, _ = self.clean([hyp([self.ids[0]], counter_evidence=[self.ids[0], self.ids[1], 777])]); self.assertEqual(out[0]["counter"], [self.ids[1]])

    def test_a_reply_of_the_wrong_shape_is_an_error(self):
        for bad in (None, {"x": 1}, "text"):
            with self.assertRaises(ValueError): im.clean(bad, self.ev())


class Generating(Setup):
    def run_(self, items, **kw):
        with mock.patch("litellm.completion", return_value=reply(items)) as comp: return im.generate(self.pid), comp

    def test_a_cited_hypothesis_is_stored_and_listed_with_its_evidence(self):
        r, _ = self.run_([hyp([self.ids[0], self.ids[1]])]); self.assertEqual((r["new"], r["updated"]), (1, 0))
        out = im.listing(self.pid); self.assertEqual(len(out["hypotheses"]), 1); self.assertEqual(set(out["citations"]), {str(self.ids[0]), str(self.ids[1])})
        self.assertEqual(out["hypotheses"][0]["status"], "new"); self.assertIn("Claim number", out["citations"][str(self.ids[0])]["claim"])

    def test_the_same_idea_again_adds_evidence_instead_of_a_duplicate(self):
        self.run_([hyp([self.ids[0]])]); r, _ = self.run_([hyp([self.ids[1]], headline="Chunked prefill may cut serving latency")])
        self.assertEqual((r["new"], r["updated"]), (0, 1)); h1 = im.listing(self.pid)["hypotheses"]; self.assertEqual(len(h1), 1); self.assertEqual(set(h1[0]["evidence"]), {self.ids[0], self.ids[1]})

    def test_too_little_evidence_means_no_model_call_and_a_plain_message(self):
        db.x("DELETE FROM developments WHERE id>?", (self.ids[1],))
        r, comp = self.run_([hyp([self.ids[0]])]); self.assertEqual(comp.call_count, 0); self.assertIn("Not enough", r["message"]); self.assertEqual(im.listing(self.pid)["hypotheses"], [])

    def test_the_prompt_carries_the_project_the_evidence_numbers_and_the_guard(self):
        _, comp = self.run_([]); p = comp.call_args.kwargs["messages"][0]["content"]
        for needle in ("vLLM Architecture Exploration", f"[{self.ids[0]}]", "Do not invent", "untrusted text", "TRENDS"): self.assertIn(needle, p)

    def test_a_project_tied_to_private_repositories_is_thought_about_locally(self):
        db.x("INSERT INTO project_links(project_id,kind,url,private) VALUES(?,?,?,1)", (self.pid, "github", "https://github.com/me/private")); models = []
        def fake(**kw): models.append(kw["model"]); return reply([])
        with mock.patch("litellm.completion", side_effect=fake): im.generate(self.pid)
        self.assertTrue(models and all(m.startswith("ollama") for m in models))

    def test_busy_models_surface_as_unavailable_not_as_a_fake_result(self):
        with mock.patch("litellm.completion", side_effect=RuntimeError("429 rate limit")):
            with self.assertRaises(llm.Unavailable): im.generate(self.pid)
        self.assertEqual(im.listing(self.pid)["hypotheses"], [])


class Reviewing(Setup):
    def make(self):
        with mock.patch("litellm.completion", return_value=reply([hyp([self.ids[0]])])): im.generate(self.pid)
        return im.listing(self.pid)["hypotheses"][0]["id"]

    def test_accepting_makes_a_project_action_once(self):
        hid = self.make(); im.accept(hid); im.accept(hid)
        items = db.q("SELECT * FROM items WHERE project_id=?", (self.pid,)); self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["kind"], items[0]["done"]), ("action", 0)); self.assertIn("Add a long-prompt case", items[0]["text"]); self.assertIn("Chunked prefill", items[0]["text"])
        self.assertEqual(db.q("SELECT status, item_id FROM hypotheses WHERE id=?", (hid,), one=True), {"status": "accepted", "item_id": items[0]["id"]})

    def test_dismissing_records_why_and_stops_it_coming_back_as_new(self):
        hid = self.make(); im.dismiss(hid, "Not relevant to CPU work"); row = db.q("SELECT * FROM hypotheses WHERE id=?", (hid,), one=True)
        self.assertEqual((row["status"], row["reason"]), ("dismissed", "Not relevant to CPU work")); self.assertEqual(im.listing(self.pid, "new")["hypotheses"], [])

    def test_unknown_ids_are_404s(self):
        self.assertEqual(c.post("/api/implications/9999/accept").status_code, 404); self.assertEqual(c.post("/api/implications/9999/dismiss", json={}).status_code, 404)


class Api(Setup):
    def test_run_list_accept_through_the_api_and_a_phone_may_review_but_not_start_a_run(self):
        with mock.patch("litellm.completion", return_value=reply([hyp([self.ids[0], self.ids[1]])])), mock.patch.object(h.api, "bg", lambda fn, *a: fn(*a)):
            self.assertTrue(c.post(f"/api/projects/{self.pid}/implications/run").json()["started"])
        last = c.get("/api/implications/status").json(); self.assertFalse(last["running"]); self.assertEqual(last["last"]["new"], 1)
        listing = c.get(f"/api/projects/{self.pid}/implications").json(); hid = listing["hypotheses"][0]["id"]
        self.assertEqual(c.post(f"/api/implications/{hid}/accept").json()["status"], "accepted")
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get(f"/api/projects/{self.pid}/implications", headers=VIA).status_code, 200)
        self.assertEqual(c.post(f"/api/implications/{hid}/dismiss", json={}, headers=VIA).status_code, 200)
        self.assertEqual(c.post(f"/api/projects/{self.pid}/implications/run", headers=VIA).status_code, 403)

    def test_hypotheses_travel_with_a_backup_and_go_with_the_project(self):
        self.assertIn("hypotheses", h.api.TABLES)


if __name__ == "__main__":
    unittest.main()
