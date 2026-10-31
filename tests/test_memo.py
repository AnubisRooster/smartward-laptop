import json, time, unittest
from types import SimpleNamespace as NS
from unittest import mock
from sw import chat, db, events, implications as im, memo
from tests import helpers as h
from tests.test_implications import dev, hyp, project, reply

c = h.client
NOW = time.time()


def answer(obj): return NS(choices=[NS(message=NS(content=json.dumps(obj)))], usage=NS(prompt_tokens=1, completion_tokens=1))


class Setup(unittest.TestCase):
    def setUp(self):
        h.reset(); events.reset(); memo.STATE.update(running=False, message=""); im.STATE.update(running=False, message="")
        db.set_setting("api_key", "sk-test"); db.set_setting("model", "openrouter/openrouter/free")
        self.src = h.add_source("Lab blog"); self.arts = [h.add_article(self.src, f"Story {i}", "x" * 600) for i in range(6)]
        self.pid = project(); self.ids = [dev(a, claim=f"Chunked prefill claim number {i}.", evidence="measured" if i < 3 else "claimed") for i, a in enumerate(self.arts)]
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()

    def memo_reply(self, **kw):
        base = {"shifted": [{"text": "Chunked prefill results keep improving.", "evidence": [self.ids[0], self.ids[1]]}],
                "projects": [{"project": f"P{self.pid}", "text": "Long prompts may deserve a benchmark case.", "evidence": [self.ids[0]]}],
                "watch": [{"text": "Whether vLLM makes it the default.", "evidence": [self.ids[3]]}],
                "questions": [{"text": "Is prefill or decode the bottleneck for us?", "evidence": []}]}
        base.update(kw); return answer(base)


class Gathering(Setup):
    def test_private_articles_and_projects_tied_to_private_repositories_are_left_out_and_counted(self):
        secret = h.add_article(self.src, "Private notes", "x" * 600, private=1); dev(secret, claim="Secret claim.")
        p2 = project(name="Secret project"); db.x("INSERT INTO project_links(project_id,kind,url,private) VALUES(?,?,?,1)", (p2, "github", "https://github.com/me/secret"))
        g = memo.gather(NOW)
        self.assertNotIn("Secret claim.", [r["claim"] for r in g["devs"]]); self.assertNotIn(p2, [p["id"] for p in g["projects"]])
        self.assertEqual(g["left_out"], {"private_articles": 1, "private_projects": 1})
        self.assertNotIn("Secret", memo._prompt(g))

    def test_a_quiet_week_widens_to_two_and_measured_comes_first(self):
        db.x("UPDATE developments SET ts=?", (NOW - 10 * 86400,))
        g = memo.gather(NOW); self.assertEqual(len(g["devs"]), 6); self.assertEqual(g["devs"][0]["evidence"], "measured")


class Cleaning(Setup):
    def test_points_keep_only_real_citations_and_a_point_left_without_any_is_dropped(self):
        g = memo.gather(NOW)
        out, dropped = memo.clean({"shifted": [{"text": "Real.", "evidence": [self.ids[0], 99999]}, {"text": "Made up.", "evidence": [99999]}, "junk"],
                                   "projects": [{"project": "P424242", "text": "Unknown project.", "evidence": [self.ids[0]]}],
                                   "questions": [{"text": "An open question needs no citation.", "evidence": []}]}, g)
        self.assertEqual(out["shifted"], [{"text": "Real.", "evidence": [self.ids[0]]}]); self.assertEqual(out["projects"], []); self.assertEqual(len(out["questions"]), 1); self.assertEqual(dropped, 3)

    def test_strong_wording_on_thin_evidence_is_flagged(self):
        out, _ = memo.clean({"shifted": [{"text": "This proves CPUs will win.", "evidence": [self.ids[3]]}, {"text": "This proves it.", "evidence": [self.ids[0], self.ids[1]]}]}, memo.gather(NOW))
        self.assertTrue(out["shifted"][0].get("caution")); self.assertNotIn("caution", out["shifted"][1])

    def test_a_memo_with_nothing_cited_is_an_error_not_an_empty_memo(self):
        with self.assertRaises(ValueError): memo.clean({"questions": [{"text": "Only a question.", "evidence": []}]}, memo.gather(NOW))
        with self.assertRaises(ValueError): memo.clean(["wrong shape"], memo.gather(NOW))


class Writing(Setup):
    def test_a_memo_is_stored_for_the_week_with_its_citations_and_rewriting_replaces_it(self):
        with mock.patch("litellm.completion", return_value=self.memo_reply()) as comp: m = memo.generate(NOW)
        self.assertEqual(m["week"], memo.week_key(NOW)); self.assertEqual(m["projects"][0]["project"], "vLLM Architecture Exploration")
        self.assertEqual(set(m["citations"]), {str(self.ids[0]), str(self.ids[1]), str(self.ids[3])}); self.assertIn("title", m["citations"][str(self.ids[0])])
        self.assertTrue(comp.call_args.kwargs["model"].startswith("openrouter/"))           # public material: the analysis model
        with mock.patch("litellm.completion", return_value=self.memo_reply(watch=[])): memo.generate(NOW)
        self.assertEqual(db.q("SELECT COUNT(*) n FROM memos", one=True)["n"], 1); self.assertEqual(memo.get()["watch"], [])

    def test_too_few_developments_is_a_plain_message_with_no_model_call(self):
        db.x("DELETE FROM developments")
        with mock.patch("litellm.completion") as comp, self.assertRaises(ValueError) as e: memo.generate(NOW)
        comp.assert_not_called(); self.assertIn("Not enough", str(e.exception))

    def test_due_only_when_turned_on_on_or_after_its_day_and_not_yet_written(self):
        self.assertFalse(memo.due(NOW)); db.set_setting("memo_auto", True); db.set_setting("memo_day", 0)
        self.assertTrue(memo.due(NOW))
        db.set_setting("memo_day", 6); self.assertEqual(memo.due(NOW), time.localtime(NOW).tm_wday == 6)
        db.set_setting("memo_day", 0)
        with mock.patch("litellm.completion", return_value=self.memo_reply()): memo.generate(NOW)
        self.assertFalse(memo.due(NOW))

    def test_a_new_memo_is_announced_once(self):
        db.set_setting("notify_articles", False); events.poll()
        with mock.patch("litellm.completion", return_value=self.memo_reply()): memo.generate(NOW)
        self.assertEqual([e["kind"] for e in events.poll()], ["memo"]); self.assertEqual(events.poll(), [])


class Api(Setup):
    def test_write_and_read_through_the_api_and_a_phone_may_read_but_not_write(self):
        with mock.patch("litellm.completion", return_value=self.memo_reply()), mock.patch.object(h.api, "bg", lambda fn, *a: fn(*a)):
            self.assertTrue(c.post("/api/memo/run").json()["started"])
        st = c.get("/api/memo/status").json(); self.assertFalse(st["running"]); self.assertEqual(st["last"]["week"], memo.week_key(time.time()))
        lst = c.get("/api/memos").json(); mid = lst["memos"][0]["id"]; self.assertEqual(lst["latest"]["id"], mid)
        self.assertEqual(c.get(f"/api/memos/{mid}").json()["shifted"][0]["text"], "Chunked prefill results keep improving.")
        self.assertEqual(c.get("/api/memos/999").status_code, 404)
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get("/api/memos", headers=VIA).status_code, 200); self.assertEqual(c.get(f"/api/memos/{mid}", headers=VIA).status_code, 200)
        self.assertEqual(c.post("/api/memo/run", headers=VIA).status_code, 403); self.assertEqual(c.post("/api/implications/review", headers=VIA).status_code, 403)

    def test_memos_and_checks_travel_with_a_backup(self):
        self.assertIn("memos", h.api.TABLES); self.assertIn("hypothesis_checks", h.api.TABLES)


class WereWeRight(Setup):
    def accepted(self, **kw):
        with mock.patch("litellm.completion", return_value=reply([hyp([self.ids[0]], **kw)])): im.generate(self.pid)
        hid = db.q("SELECT id FROM hypotheses", one=True)["id"]; im.accept(hid)
        db.x("UPDATE hypotheses SET created=? WHERE id=?", (NOW - 20 * 86400, hid)); return hid

    def later(self, claim, evidence="measured", days=1):
        return dev(h.add_article(self.src, f"Later {claim}", "x" * 600), claim=claim, evidence=evidence, days=days)

    def test_candidates_are_newer_related_unseen_developments_in_the_projects_domains(self):
        hid = self.accepted(); rel = self.later("Chunked prefill cuts latency for long prompts.")
        self.later("Robots fold laundry.")                                                                   # nothing in common
        other = dev(h.add_article(self.src, "Elsewhere", "x" * 600), claim="Chunked prefill benchmark for long prompts.", domains=("Frontier models",))
        hrow = db.q("SELECT * FROM hypotheses WHERE id=?", (hid,), one=True); hrow["evidence"] = json.loads(hrow["evidence"])
        ids = [r["id"] for r in im.candidates(hrow, db.q("SELECT * FROM projects", one=True), NOW)]
        self.assertIn(rel, ids); self.assertNotIn(other, ids); self.assertNotIn(self.ids[0], ids)       # its own evidence is not new evidence

    def test_labels_for_ids_not_given_are_ignored(self):
        cands = [{"id": 5}, {"id": 6}]
        out = im.clean_labels({"labels": [{"id": 5, "label": "supports", "why": "same"}, {"id": 9, "label": "contradicts"}, {"id": 6, "label": "maybe"}, "x"]}, cands)
        self.assertEqual(out, {5: ("supports", "same")})

    def test_the_verdict_needs_more_than_one_claim_and_weighs_measurements(self):
        m, cl = {"evidence": "measured"}, {"evidence": "claimed"}
        self.assertEqual(im.verdict([cl], []), "open"); self.assertEqual(im.verdict([m], []), "supported"); self.assertEqual(im.verdict([cl, cl], [cl]), "open")
        self.assertEqual(im.verdict([cl], [m]), "contradicted"); self.assertEqual(im.verdict([], [cl]), "open")

    def test_a_check_records_a_verdict_adds_up_over_time_and_shows_on_the_listing(self):
        hid = self.accepted(); a = self.later("Chunked prefill cuts latency for long prompts.", evidence="claimed")
        with mock.patch("litellm.completion", return_value=answer({"labels": [{"id": a, "label": "supports", "why": "same effect"}]})): first = im.check(hid, NOW)
        self.assertEqual(first["verdict"], "open")
        b = self.later("Chunked prefill gives long prompts lower latency again.", evidence="claimed")
        with mock.patch("litellm.completion", return_value=answer({"labels": [{"id": b, "label": "supports"}]})) as comp: second = im.check(hid, NOW)
        self.assertNotIn(f"[{a}]", comp.call_args.kwargs["messages"][0]["content"])                       # already looked at
        self.assertEqual(second["verdict"], "supported")
        with mock.patch("litellm.completion") as comp: self.assertIsNone(im.check(hid, NOW)); comp.assert_not_called()   # nothing new: no call, no row
        r = im.listing(self.pid)["hypotheses"][0]; self.assertEqual(r["standing"]["verdict"], "supported"); self.assertEqual(r["standing"]["supports"], [a, b])
        self.assertIn(str(b), im.listing(self.pid)["citations"])

    def test_review_checks_accepted_only_and_the_memo_reports_how_they_stand(self):
        hid = self.accepted(); a = self.later("Chunked prefill cuts latency for long prompts.")
        def fake(**kw):
            msg = kw["messages"][0]["content"]
            return answer({"labels": [{"id": a, "label": "supports"}]}) if msg.startswith("You check") else self.memo_reply()
        with mock.patch("litellm.completion", side_effect=fake): m = memo.generate(NOW)
        self.assertEqual(m["review"]["checked"], 1); self.assertEqual(m["standing"], [{"id": hid, "project": "vLLM Architecture Exploration", "headline": hyp([])["headline"], "verdict": "supported"}])

    def test_dismissed_ideas_and_why_are_passed_on_so_they_are_not_proposed_again(self):
        with mock.patch("litellm.completion", return_value=reply([hyp([self.ids[0]])])): im.generate(self.pid)
        im.dismiss(db.q("SELECT id FROM hypotheses", one=True)["id"], "we don't do long prompts")
        with mock.patch("litellm.completion", return_value=reply([])) as comp: im.generate(self.pid)
        p = comp.call_args.kwargs["messages"][0]["content"]; self.assertIn("DISMISSED BEFORE", p); self.assertIn("we don't do long prompts", p)

    def test_deleting_a_project_removes_its_checks(self):
        hid = self.accepted(); db.x("INSERT INTO hypothesis_checks(hid,ts,verdict) VALUES(?,?,?)", (hid, NOW, "open"))
        c.delete(f"/api/projects/{self.pid}"); self.assertEqual(db.q("SELECT COUNT(*) n FROM hypothesis_checks", one=True)["n"], 0)


class StrategistTool(Setup):
    def test_what_shifted_returns_cited_public_developments_for_a_domain(self):
        secret = h.add_article(self.src, "Private notes", "x" * 600, private=1); dev(secret, claim="Secret claim.")
        out = memo.what_shifted("serving", 2, NOW)
        self.assertEqual(out["domains"], ["Inference serving"]); claims = [d["claim"] for d in out["developments"]]
        self.assertIn("Chunked prefill claim number 0.", claims); self.assertNotIn("Secret claim.", claims); self.assertTrue(all("article_id" in d for d in out["developments"]))

    def test_the_tool_is_offered_in_the_thinking_modes_and_runs(self):
        for m in ("brainstorm", "critique", "research", "weekly"): self.assertIn("what_shifted", chat.MODES[m][2])
        conv = db.q("SELECT * FROM conversations WHERE id=?", (chat.new_conversation("brainstorm"),), one=True)
        self.assertIn("Inference serving", chat.run_tool("what_shifted", {"domain": "kv"}, conv) + chat.run_tool("what_shifted", {"domain": "serving"}, conv))


if __name__ == "__main__":
    unittest.main()
