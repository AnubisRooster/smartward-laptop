import json, time, unittest
from types import SimpleNamespace as NS
from unittest import mock
from sw import db, developments as dv, llm, signals
from tests import helpers as h

c = h.client
TEXT = ("vLLM 0.12 adds chunked prefill for long prompts. On an H100 the team measured 2.1x higher throughput than vLLM 0.9 on the ShareGPT workload. "
        "The release is available today under the Apache license. " * 4)


def item(**kw):
    base = {"kind": "efficiency", "subject": "vLLM 0.12", "claim": "Chunked prefill raises throughput.", "metric": "throughput", "value": "2.1x", "baseline": "vLLM 0.9",
            "evidence": "measured", "domains": ["Inference serving"], "quote": "measured 2.1x higher throughput than vLLM 0.9 on the ShareGPT workload"}
    base.update(kw); return base


def reply(items): return NS(choices=[NS(message=NS(content=json.dumps({"developments": items})))], usage=NS(prompt_tokens=1, completion_tokens=1))


def article(**kw):
    a = {"id": 1, "title": "vLLM 0.12 released", "text": TEXT, "teaser": "", "published": time.time(), "private": 0, "source": "vLLM releases"}; a.update(kw); return a


class Cleaning(unittest.TestCase):
    def setUp(self): h.reset(); self.ds = signals.domains()

    def clean(self, items, **kw): return dv.clean(article(**kw), {"developments": items}, self.ds)

    def test_a_well_grounded_measured_development_is_kept_as_it_is(self):
        out, dropped = self.clean([item()]); self.assertEqual(dropped, 0)
        self.assertEqual((out[0]["kind"], out[0]["evidence"], out[0]["grounded"], out[0]["domains"]), ("efficiency", "measured", True, ["Inference serving"]))

    def test_a_quote_with_an_ellipsis_or_a_changed_quote_mark_still_counts_but_a_paraphrase_does_not(self):
        body = _norm_text = "We scale lattice quantization to billion parameter models. The method consistently improves accuracy across tasks, with gains of up to 6.7 points."
        a = article(text=body)
        ok, _ = dv.clean(a, {"developments": [item(quote="We scale lattice quantization to billion-parameter models ... consistently improves accuracy across tasks, with gains of up to 6.7 points")]}, self.ds)
        self.assertTrue(ok[0]["grounded"])
        bad, _ = dv.clean(a, {"developments": [item(quote="Researchers demonstrate that large networks can be compressed dramatically with almost no loss")]}, self.ds)
        self.assertFalse(bad[0]["grounded"])

    def test_a_bare_list_is_accepted_as_the_answer(self):
        out, _ = dv.clean(article(), [item()], self.ds); self.assertEqual(len(out), 1)
        out, _ = dv.clean(article(), {"items": [item()]}, self.ds); self.assertEqual(len(out), 1)

    def test_a_domain_the_model_guessed_without_its_words_appearing_is_dropped(self):
        out, _ = self.clean([item(domains=["Local & CPU inference"], claim="A two-player game syncs phones with audio chirps.", subject="Chirp Pong", quote="measured 2.1x higher throughput than vLLM 0.9 on the ShareGPT workload")])
        self.assertEqual(out[0]["domains"], [])

    def test_retagging_applies_the_current_keywords_to_what_is_already_stored(self):
        s = h.add_source("B"); aid = h.add_article(s, "Game on a phone", TEXT)
        db.x("INSERT INTO developments(article_id,kind,claim,subject,quote,evidence,grounded,domains,ts,created,model) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (aid, "capability", "A game syncs phones by sound.", "Chirp", "q", "claimed", 1, json.dumps(["Local & CPU inference", "Enterprise AI"]), 1.0, 1.0, "m"))
        self.assertEqual(dv.retag(), 1); self.assertEqual(json.loads(db.q("SELECT domains FROM developments", one=True)["domains"]), []); self.assertEqual(dv.retag(), 0)

    def test_tagging_every_domain_keeps_only_the_two_whose_words_appear(self):
        names = [d["name"] for d in self.ds]
        out, _ = self.clean([item(domains=names, claim="Chunked prefill raises serving throughput.", quote="measured 2.1x higher throughput than vLLM 0.9 on the ShareGPT workload")])
        self.assertLessEqual(len(out[0]["domains"]), 2); self.assertIn("Inference serving", out[0]["domains"]); self.assertNotIn("Enterprise AI", out[0]["domains"])

    def test_a_quote_that_is_not_in_the_article_makes_it_ungrounded_and_unproven(self):
        out, _ = self.clean([item(quote="the team achieved a 10x speedup on every workload")])
        self.assertFalse(out[0]["grounded"]); self.assertEqual(out[0]["evidence"], "anecdotal"); self.assertEqual(out[0]["claimed_evidence"], "measured")

    def test_no_quote_at_all_is_ungrounded(self):
        self.assertFalse(self.clean([item(quote="")])[0][0]["grounded"]); self.assertFalse(self.clean([item(quote="vLLM")])[0][0]["grounded"])       # too short to prove anything

    def test_measured_without_a_number_is_only_claimed(self):
        self.assertEqual(self.clean([item(value="")])[0][0]["evidence"], "claimed")

    def test_unknown_kinds_empty_claims_and_junk_are_dropped_and_counted(self):
        out, dropped = self.clean([item(kind="magic"), item(claim=""), "junk", item()]); self.assertEqual(len(out), 1); self.assertEqual(dropped, 3)

    def test_domains_not_in_your_list_are_ignored_and_the_case_does_not_matter(self):
        out, _ = self.clean([item(domains=["inference serving", "Made up domain"])]); self.assertEqual(out[0]["domains"], ["Inference serving"])

    def test_at_most_four_per_article_and_long_text_is_trimmed(self):
        out, _ = self.clean([item(claim="x" * 900) for _ in range(9)]); self.assertEqual(len(out), 4); self.assertEqual(len(out[0]["claim"]), 300)

    def test_something_that_is_not_the_expected_shape_is_an_error(self):
        for bad in (None, {"entities": [], "x": 1}, {"developments": "x"}, "text"):
            with self.assertRaises(ValueError): dv.clean(article(), bad, self.ds)

    def test_an_empty_list_is_a_valid_answer(self): self.assertEqual(self.clean([]), ([], 0))


class Running(unittest.TestCase):
    def setUp(self):
        h.reset(); db.set_setting("model", "openrouter/openrouter/free"); db.set_setting("api_key", "sk-test"); self.src = h.add_source("Blog")
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()

    def add(self, n, **cols):
        return [h.add_article(self.src, f"vLLM story {i}", TEXT, published=time.time() - i * 100, **cols) for i in range(n)]

    def test_it_reads_stores_and_does_not_read_twice(self):
        ids = self.add(4)
        with mock.patch("litellm.completion", return_value=reply([item()])) as comp: r = dv.run(ids, workers=2)
        self.assertEqual((r["done"], r["paused"], r["failed"]), (4, False, 0)); self.assertEqual(len(dv.listing()), 4)
        with mock.patch("litellm.completion", return_value=reply([item()])) as comp: dv.run(workers=2)
        self.assertEqual(comp.call_count, 0)                                                         # everything has been read already

    def test_a_busy_model_pauses_without_marking_anything_read(self):
        ids = self.add(4)
        with mock.patch("litellm.completion", side_effect=RuntimeError("429 rate limit")): r = dv.run(ids, workers=2)
        self.assertTrue(r["paused"]); self.assertEqual(db.q("SELECT COUNT(*) n FROM development_runs", one=True)["n"], 0)

    def test_an_unreadable_answer_is_recorded_as_failed_for_that_article_only(self):
        ids = self.add(3); n = [0]
        def fake(**kw):
            n[0] += 1; return NS(choices=[NS(message=NS(content="no json here"))], usage=NS(prompt_tokens=1, completion_tokens=1)) if n[0] <= 2 else reply([item()])   # the first article is unreadable on both tries
        with mock.patch("litellm.completion", side_effect=fake): r = dv.run(ids, workers=1)
        self.assertEqual(r["failed"], 1); self.assertEqual(db.q("SELECT COUNT(*) n FROM development_runs WHERE status LIKE 'failed%'", one=True)["n"], 1)
        self.assertEqual(len(dv.listing()), 2)

    def test_private_articles_are_read_by_the_local_model_only(self):
        ids = self.add(2, private=1); models = []
        def fake(**kw): models.append(kw["model"]); return reply([])
        with mock.patch("litellm.completion", side_effect=fake): dv.run(ids, workers=1)
        self.assertTrue(models and all(m.startswith("ollama") for m in models))

    def test_the_reading_prompt_carries_the_article_the_domains_and_the_guard(self):
        ids = self.add(1); seen = {}
        def fake(**kw): seen.update(kw); return reply([])
        with mock.patch("litellm.completion", side_effect=fake): dv.run(ids, workers=1)
        p = seen["messages"][0]["content"]; self.assertIn("vLLM story 0", p); self.assertIn("KV cache", p); self.assertIn("untrusted data", p); self.assertEqual(seen["model"], "openrouter/poolside/laguna-s-2.1:free")

    def test_re_reading_an_article_replaces_its_old_developments(self):
        ids = self.add(1)
        with mock.patch("litellm.completion", return_value=reply([item(), item(claim="Second.")])): dv.run(ids)
        a = db.q("SELECT a.*, 'x' source FROM articles a WHERE id=?", (ids[0],), one=True); dv.store(a, [dv.clean(a, {"developments": [item()]}, signals.domains())[0][0]], "m")
        self.assertEqual(len(dv.listing(article_id=ids[0])), 1)


class Sampling(unittest.TestCase):
    def setUp(self): h.reset()

    def test_a_spread_across_kinds_of_source_that_skips_private_short_old_and_already_read(self):
        arx, lab, blog = h.add_source("arXiv: x", kind="arxiv"), h.add_source("OpenAI"), h.add_source("Some blog")
        now = time.time()
        for s, k in ((arx, "paper"), (lab, "lab"), (blog, "blog")):
            for i in range(12): h.add_article(s, f"{k} KV cache story {i}", TEXT, published=now - i * 3600)
        junk = [h.add_article(blog, "private", TEXT, published=now, private=1), h.add_article(blog, "short", "tiny", published=now), h.add_article(blog, "old", TEXT, published=now - 200 * 86400)]
        read = h.add_article(blog, "already read", TEXT, published=now); db.x("INSERT INTO development_runs(article_id,ts,status,model,n) VALUES(?,?,?,?,0)", (read, now, "ok", "m"))
        ids = dv.sample(30); self.assertEqual(len(ids), 30 if False else len(set(ids)))
        for j in junk + [read]: self.assertNotIn(j, ids)
        classes = {signals.source_class(r["skind"], r["sname"]) for r in db.q(f"SELECT s.kind skind, s.name sname FROM articles a JOIN sources s ON s.id=a.source_id WHERE a.id IN ({','.join('?' * len(ids))})", ids)}
        self.assertEqual(classes, {"paper", "lab", "blog"})


class Api(unittest.TestCase):
    def setUp(self): h.reset(); db.set_setting("api_key", "sk-test")

    def test_starting_a_sample_reading_it_and_listing_it(self):
        s = h.add_source("Blog")
        for i in range(5): h.add_article(s, f"vLLM story {i}", TEXT, published=time.time() - i * 60)
        with mock.patch("litellm.completion", return_value=reply([item()])), mock.patch("sw.llm.time.sleep"), mock.patch.object(h.api, "bg", lambda fn, *a: fn(*a)):   # tests make bg a no-op; run it inline here
            r = c.post("/api/developments/run", json={"sample": 3}); self.assertEqual(r.json(), {"started": True, "articles": 3})
        st = c.get("/api/developments/status").json(); self.assertEqual((st["read"], st["developments"]), (3, 3))
        rows = c.get("/api/developments").json(); self.assertEqual(rows[0]["kind"], "efficiency"); self.assertTrue(rows[0]["grounded"]); self.assertEqual(rows[0]["domains"], ["Inference serving"])
        self.assertEqual(len(c.get("/api/developments", params={"domain": "Inference serving"}).json()), 3); self.assertEqual(c.get("/api/developments", params={"domain": "KV cache"}).json(), [])

    def test_a_phone_may_read_developments_but_not_start_a_reading_run(self):
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get("/api/developments", headers=VIA).status_code, 200); self.assertEqual(c.post("/api/developments/run", json={"sample": 3}, headers=VIA).status_code, 403)


if __name__ == "__main__":
    unittest.main()


class Salvage(unittest.TestCase):
    def setUp(self): h.reset(); self.ds = signals.domains()

    def test_a_reply_cut_off_in_the_middle_keeps_the_complete_developments(self):
        full = json.dumps({"developments": [item(), item(claim="Second one is fine.")]})
        got = dv.salvage(full[:full.rindex('"claim"') + 20])           # cut inside the second item
        self.assertEqual(len(got["developments"]), 1)

    def test_one_broken_item_does_not_lose_the_others(self):
        raw = '{"developments":[' + json.dumps(item()) + ', {"kind": "capability", "claim": "oops "quoted" badly"}, ' + json.dumps(item(claim="Third.")) + ']}'
        self.assertEqual([d["claim"] for d in dv.salvage(raw)["developments"]], ["Chunked prefill raises throughput.", "Third."])

    def test_braces_inside_text_do_not_confuse_it(self):
        raw = '{"developments":[' + json.dumps(item(claim='Supports {braces} and "quotes" in text.')) + ']}'
        self.assertIn("{braces}", dv.salvage(raw)["developments"][0]["claim"])

    def test_nothing_usable_is_none(self):
        for raw in ("", "no json", '{"developments":[]}', '{"developments":[{"kind": '): self.assertIsNone(dv.salvage(raw))

    def test_an_empty_reply_is_tried_again_and_a_cut_off_one_is_salvaged(self):
        h.reset(); db.set_setting("api_key", "sk-test"); s = h.add_source("B"); aid = h.add_article(s, "vLLM", TEXT)
        a = db.q("SELECT a.*, 'B' source FROM articles a WHERE id=?", (aid,), one=True)
        full = json.dumps({"developments": [item(), item(claim="Second.")]}); replies = iter(["", full[:-30]])
        with mock.patch("sw.llm.text", side_effect=lambda *x, **k: next(replies)):
            out, _ = dv._ask(a, self.ds)
        self.assertGreaterEqual(len(out), 1)
        with mock.patch("sw.llm.text", return_value=""):
            with self.assertRaises(ValueError): dv._ask(a, self.ds)


class ByTheSourceOfTheArticle(unittest.TestCase):
    def test_a_run_can_be_limited_to_chosen_sources(self):
        h.reset(); db.set_setting("api_key", "sk-test"); a, b = h.add_source("A"), h.add_source("B")
        ia = [h.add_article(a, f"a{i}", TEXT) for i in range(3)]; ib = [h.add_article(b, f"b{i}", TEXT) for i in range(3)]
        with mock.patch("litellm.completion", return_value=reply([item()])), mock.patch("sw.llm.time.sleep"): r = dv.run(source_ids=[b], workers=1)
        self.assertEqual(r["done"], 3); self.assertEqual({d["article_id"] for d in dv.listing()}, set(ib))
