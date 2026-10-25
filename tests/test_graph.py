import json, unittest
from unittest import mock
from sw import graph
from tests import helpers as h

c = h.client


class GraphTests(unittest.TestCase):
    def setUp(self):
        h.reset()
        self.src = h.add_source("Blog")
        self.a1 = h.add_article(self.src, "Post one", "x"); self.a2 = h.add_article(self.src, "Post two", "y")

    def mention(self, aid, tid): h.db.x("INSERT INTO mentions(article_id,theme_id,ts) VALUES(?,?,?)", (aid, tid, h.db.now()))

    def test_a_theme_is_found_again_by_its_normalized_name(self):
        a = graph.resolve("vLLM", "tool")
        self.assertEqual(graph.resolve("  vllm ", "tool"), a)
        self.assertNotEqual(graph.resolve("Medusa", "technique"), a)
        self.assertIsNone(graph.resolve("   "))

    def test_rename_keeps_the_old_name_as_an_alias_and_merges_on_a_clash(self):
        a = graph.resolve("PagedAttention", "technique")
        graph.rename(a, "Paged attention")
        detail = c.get(f"/api/themes/{a}").json()
        self.assertEqual(detail["name"], "Paged attention"); self.assertIn("pagedattention", detail["aliases"])
        self.assertEqual(graph.resolve("PagedAttention", "technique"), a, "the old name still resolves to it")
        b = graph.resolve("Paged-attention v2", "technique")
        self.mention(self.a1, b)
        self.assertEqual(graph.rename(b, "Paged attention"), a)
        self.assertIsNone(h.db.q("SELECT 1 FROM themes WHERE id=?", (b,), one=True))
        self.assertEqual(h.db.q("SELECT theme_id FROM mentions", one=True)["theme_id"], a)

    def test_merge_moves_mentions_and_edges_and_drops_self_edges(self):
        a, b, other = (graph.resolve(n, "tool") for n in ("A tool", "B tool", "Other"))
        self.mention(self.a1, a); self.mention(self.a2, b)
        h.db.x("INSERT INTO edges(a,b,relation,article_id,ts) VALUES(?,?,?,?,?)", (a, b, "related_to", self.a1, 0))
        h.db.x("INSERT INTO edges(a,b,relation,article_id,ts) VALUES(?,?,?,?,?)", (b, other, "uses", self.a2, 0))
        c.post(f"/api/themes/{b}/merge", json={"into": a})
        self.assertEqual({r["theme_id"] for r in h.db.q("SELECT theme_id FROM mentions")}, {a})
        edges = h.db.q("SELECT a,b FROM edges")
        self.assertEqual([(e["a"], e["b"]) for e in edges], [(a, other)])

    def test_split_moves_only_the_chosen_articles(self):
        t = graph.resolve("Inference", "concept")
        self.mention(self.a1, t); self.mention(self.a2, t)
        new = c.post(f"/api/themes/{t}/split", json={"name": "Serving", "article_ids": [self.a2]}).json()["id"]
        by = {r["article_id"]: r["theme_id"] for r in h.db.q("SELECT article_id,theme_id FROM mentions")}
        self.assertEqual(by, {self.a1: t, self.a2: new})

    def test_the_theme_list_and_graph_view_respond(self):
        a, b = graph.resolve("Alpha", "tool"), graph.resolve("Beta", "tool")
        self.mention(self.a1, a); self.mention(self.a1, b)
        h.db.x("INSERT INTO edges(a,b,relation,article_id,ts) VALUES(?,?,?,?,?)", (a, b, "related_to", self.a1, h.db.now()))
        self.assertEqual([t["name"] for t in c.get("/api/themes").json()], ["Alpha", "Beta"])
        view = c.get("/api/graph").json()
        self.assertEqual({t["name"] for t in view["themes"]}, {"Alpha", "Beta"}); self.assertEqual(len(view["edges"]), 1)
        self.assertEqual(c.get("/api/themes/9999").status_code, 404)

    def test_the_digest_is_empty_until_there_is_something_new(self):
        h.db.x("DELETE FROM articles")
        self.assertEqual(c.get("/api/digest").json()["clusters"], [])

    def test_a_digest_groups_new_articles_by_theme(self):
        ids = [h.add_article(self.src, f"Speculative post {i}", "x") for i in range(5)]
        t = graph.resolve("Speculative decoding", "technique")
        for i in ids[:3]: self.mention(i, t)
        with mock.patch.object(graph, "_summarize_digest"):
            data = c.get("/api/digest", params={"rebuild": True}).json()
        top = data["clusters"][0]
        self.assertEqual((top["theme"], sorted(top["article_ids"])), ("Speculative decoding", sorted(ids[:3])))
        self.assertEqual(h.db.q("SELECT COUNT(*) n FROM digests", one=True)["n"], 1)


if __name__ == "__main__":
    unittest.main()
