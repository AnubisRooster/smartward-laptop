import unittest
from sw import db, events
from tests import helpers as h

c = h.client


class SearchTests(unittest.TestCase):
    def setUp(self):
        h.reset(); events.reset()
        self.src = h.add_source("Alignment Weekly")
        h.add_article(self.src, "Speculative decoding explained", "x", published=2)
        h.add_article(self.src, "Cooking with 100% butter", "x", published=1)
        db.x("INSERT INTO projects(name,goal,created,updated) VALUES('vLLM Architecture','',1,1)")

    def test_finds_each_kind_by_name_case_insensitively(self):
        r = c.get("/api/search", params={"q": "SPECULATIVE"}).json()
        self.assertEqual([a["title"] for a in r["articles"]], ["Speculative decoding explained"])
        self.assertEqual([p["name"] for p in c.get("/api/search", params={"q": "vllm"}).json()["projects"]], ["vLLM Architecture"])
        self.assertEqual([s["name"] for s in c.get("/api/search", params={"q": "weekly"}).json()["sources"]], ["Alignment Weekly"])

    def test_percent_and_underscore_are_literal(self):
        self.assertEqual(len(c.get("/api/search", params={"q": "100%"}).json()["articles"]), 1)
        self.assertEqual(c.get("/api/search", params={"q": "%"}).json()["articles"][0]["title"], "Cooking with 100% butter")
        self.assertEqual(c.get("/api/search", params={"q": "_"}).json()["articles"], [])

    def test_empty_query_returns_nothing(self):
        self.assertTrue(all(v == [] for v in c.get("/api/search", params={"q": "  "}).json().values()))


class PollTests(unittest.TestCase):
    def setUp(self):
        h.reset(); events.reset()
        self.src = h.add_source("Feed")
        h.add_article(self.src, "Already here")

    def poll(self): return c.post("/api/events/poll").json()["events"]

    def test_first_poll_does_not_announce_the_existing_library(self):
        self.assertEqual(self.poll(), [])

    def test_new_articles_are_announced_once(self):
        self.poll()
        h.add_article(self.src, "Fresh one", relevance=0.9); h.add_article(self.src, "Fresh two", relevance=0.4)
        ev = self.poll()
        self.assertEqual([(e["kind"], e["count"], e["body"]) for e in ev], [("articles", 2, "Fresh one")])
        self.assertEqual(self.poll(), [])

    def test_off_topic_and_unscored_articles_are_not_announced(self):
        self.poll()
        h.add_article(self.src, "Off topic", relevant=0); h.add_article(self.src, "Not scored yet", relevance=None)
        self.assertEqual(self.poll(), [])

    def test_failing_source_is_announced_once_until_it_recovers(self):
        self.poll()
        db.x("UPDATE sources SET last_status='error', last_error='HTTP 404' WHERE id=?", (self.src,))
        self.assertEqual([e["kind"] for e in self.poll()], ["source"]); self.assertEqual(self.poll(), [])
        db.x("UPDATE sources SET last_status='ok' WHERE id=?", (self.src,)); self.poll()
        db.x("UPDATE sources SET last_status='error' WHERE id=?", (self.src,))
        self.assertEqual([e["kind"] for e in self.poll()], ["source"])

    def test_pending_approval_is_announced_once(self):
        self.poll()
        db.x("INSERT INTO approvals(id,conv_id,tool,title,detail,args,ts) VALUES('a1',1,'fetch','Read a page','u','{}',1)")
        self.assertEqual([e["kind"] for e in self.poll()], ["approval"]); self.assertEqual(self.poll(), [])

    def test_locked_app_hides_titles(self):
        self.poll(); db.set_setting("lock_enabled", True)
        h.add_article(self.src, "Secret research", relevance=0.9)
        ev = self.poll(); self.assertEqual(len(ev), 1); self.assertNotIn("Secret", ev[0]["body"] + ev[0]["title"])

    def test_each_kind_can_be_switched_off(self):
        self.poll()
        for k in ("notify_articles", "notify_sources", "notify_approvals"): db.set_setting(k, False)
        h.add_article(self.src, "Fresh", relevance=0.9)
        db.x("UPDATE sources SET last_status='error' WHERE id=?", (self.src,))
        db.x("INSERT INTO approvals(id,conv_id,tool,title,detail,args,ts) VALUES('a2',1,'fetch','x','u','{}',1)")
        self.assertEqual(self.poll(), [])


if __name__ == "__main__":
    unittest.main()
