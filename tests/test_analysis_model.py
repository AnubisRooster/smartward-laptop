import time, unittest
from types import SimpleNamespace as NS
from unittest import mock
from sw import db, graph, llm
from tests import helpers as h

GOOD = '{"entities":[{"name":"vLLM","type":"tool"},{"name":"PagedAttention","type":"technique"}],"relations":[{"a":"vLLM","b":"PagedAttention","relation":"uses"}]}'
LAGUNA, FLINT = "openrouter/poolside/laguna-s-2.1:free", "openrouter/recursive/flint-v1.0:free"


def reply(text=GOOD): return NS(choices=[NS(message=NS(content=text))], usage=NS(prompt_tokens=1, completion_tokens=1))


class Routing(unittest.TestCase):
    def setUp(self):
        h.reset(); db.set_setting("model", "openrouter/openrouter/free"); db.set_setting("api_key", "sk-test")
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()

    def test_reading_public_articles_uses_the_pinned_analysis_model_and_chat_keeps_its_own(self):
        self.assertEqual(llm.pick_model(False, "graph"), LAGUNA); self.assertEqual(llm.pick_model(False, "developments"), LAGUNA)
        self.assertEqual(llm.pick_model(False, "chat"), "openrouter/openrouter/free")

    def test_private_articles_and_other_work_stay_local(self):
        self.assertTrue(llm.pick_model(True, "graph").startswith("ollama"))
        for f in ("summary", "digest", "brief"): self.assertTrue(llm.pick_model(False, f).startswith("ollama"), f)

    def test_chat_only_scope_keeps_analysis_local_and_so_does_a_missing_key(self):
        db.set_setting("cloud_scope", "chat"); self.assertTrue(llm.pick_model(False, "graph").startswith("ollama"))
        db.set_setting("cloud_scope", "analysis"); db.set_setting("api_key", ""); self.assertNotEqual(llm.pick_model(False, "graph"), LAGUNA)

    def test_it_works_with_a_local_chat_model_too(self):
        db.set_setting("model", "ollama_chat/qwen2.5:7b"); self.assertEqual(llm.pick_model(False, "graph"), LAGUNA); self.assertEqual(llm.pick_model(False, "chat"), "ollama_chat/qwen2.5:7b")


class Fallback(unittest.TestCase):
    def setUp(self):
        h.reset(); db.set_setting("model", "openrouter/openrouter/free"); db.set_setting("api_key", "sk-test")
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop()

    def ask(self, fake): 
        with mock.patch("litellm.completion", side_effect=fake): return llm.text([{"role": "user", "content": "x"}], feature="graph")

    def test_a_rate_limited_first_model_falls_back_to_flint(self):
        seen = []
        def fake(**kw):
            seen.append(kw["model"])
            if kw["model"] == LAGUNA: raise RuntimeError("RateLimitError: 429 too many requests")
            return reply()
        self.assertEqual(self.ask(fake), GOOD); self.assertEqual(seen, [LAGUNA, FLINT])

    def test_when_every_model_is_busy_it_says_so_in_a_way_that_is_not_a_failure(self):
        with self.assertRaises(llm.Unavailable): self.ask(lambda **kw: (_ for _ in ()).throw(RuntimeError("429 rate limit")))

    def test_a_real_error_is_not_retried_on_other_models(self):
        seen = []
        def fake(**kw): seen.append(kw["model"]); raise ValueError("bad request: invalid prompt")
        with self.assertRaises(ValueError): self.ask(fake)
        self.assertEqual(seen, [LAGUNA])

    def test_analysis_calls_leave_room_for_models_that_think_first(self):
        kws = []
        def fake(**kw): kws.append(kw); return reply()
        self.ask(fake); self.assertEqual(kws[0]["max_tokens"], 3000)


class Reading(unittest.TestCase):
    def setUp(self):
        h.reset(); db.set_setting("model", "openrouter/openrouter/free"); db.set_setting("api_key", "sk-test")
        self.src = h.add_source("Blog")
        self.ids = [h.add_article(self.src, f"Article {i}", "vLLM uses PagedAttention. " * 40, published=100 + i, graph_done=0) for i in range(9)]

    def test_three_at_a_time_and_every_article_is_recorded_once(self):
        active, peak = [0], [0]; lock = __import__("threading").Lock()
        def fake(**kw):
            with lock: active[0] += 1; peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock: active[0] -= 1
            return reply()
        with mock.patch("litellm.completion", side_effect=fake): r = graph.extract_pending(workers=3)
        self.assertEqual((r["done"], r["paused"]), (9, False)); self.assertEqual(peak[0], 3)
        self.assertEqual(db.q("SELECT COUNT(*) n FROM articles WHERE graph_done=1", one=True)["n"], 9)
        self.assertEqual(db.q("SELECT COUNT(*) n FROM mentions", one=True)["n"], 18)          # two themes per article
        self.assertEqual(db.q("SELECT COUNT(*) n FROM themes", one=True)["n"], 2)             # the same two themes, not eighteen

    def test_a_busy_model_pauses_the_batch_without_marking_failures(self):
        with mock.patch("litellm.completion", side_effect=RuntimeError("429 rate limit")), mock.patch("sw.llm.time.sleep"):
            r = graph.extract_pending(workers=3)
        self.assertTrue(r["paused"]); self.assertEqual(db.q("SELECT COALESCE(SUM(graph_fails),0) n FROM articles", one=True)["n"], 0)
        self.assertEqual(db.q("SELECT COUNT(*) n FROM articles WHERE graph_done=1", one=True)["n"], 0)       # all still waiting for next time

    def test_a_bad_answer_counts_as_a_failure_for_that_article_only(self):
        n = [0]
        def fake(**kw):
            n[0] += 1; return reply("not json at all") if n[0] == 1 else reply()
        with mock.patch("litellm.completion", side_effect=fake): graph.extract_pending(workers=1)
        self.assertEqual(db.q("SELECT COUNT(*) n FROM articles WHERE graph_fails=1", one=True)["n"], 1); self.assertEqual(db.q("SELECT COUNT(*) n FROM articles WHERE graph_done=1", one=True)["n"], 8)

    def test_private_articles_are_never_sent_to_the_cloud(self):
        db.x("UPDATE articles SET private=1")
        models = []
        def fake(**kw): models.append(kw["model"]); return reply()
        with mock.patch("litellm.completion", side_effect=fake): graph.extract_pending(workers=2)
        self.assertTrue(models and all(m.startswith("ollama") for m in models))


if __name__ == "__main__":
    unittest.main()


class Reasons(unittest.TestCase):
    def test_the_reason_a_model_was_unavailable_is_shown_without_keys_or_account_ids(self):
        h.reset(); db.set_setting("api_key", "sk-or-v1-supersecretkey123"); db.set_setting("model", "openrouter/openrouter/free")
        err = RuntimeError('429 rate limit {"error":{"message":"free-models-per-min"},"user_id":"user_abc123"} key sk-or-v1-supersecretkey123')
        with mock.patch("litellm.completion", side_effect=err), mock.patch("sw.llm.time.sleep"):
            with self.assertRaises(llm.Unavailable) as cm: llm.text([{"role": "user", "content": "x"}], feature="graph")
        msg = str(cm.exception); self.assertIn("free-models-per-min", msg); self.assertNotIn("user_abc123", msg); self.assertNotIn("supersecretkey", msg)
