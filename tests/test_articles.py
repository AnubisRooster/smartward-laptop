import unittest
from tests import helpers as h

c = h.client


class ArticleTests(unittest.TestCase):
    def setUp(self):
        h.reset()
        self.src = h.add_source("Blog")
        self.a1 = h.add_article(self.src, "Speculative decoding explained", "A draft model proposes tokens that a bigger model verifies.", published=300)
        self.a2 = h.add_article(self.src, "Quantizing kernels", "Fast kernels for quantized inference.", published=200, starred=1, relevance=0.9)
        self.a3 = h.add_article(self.src, "Already read", "Old news.", published=100, read=1)
        self.a4 = h.add_article(self.src, "Off topic", "Cooking.", published=250, relevant=0)

    def ids(self, **params): return [a["id"] for a in c.get("/api/articles", params=params).json()["items"]]

    def test_unread_is_newest_first_and_hides_read_and_off_topic(self):
        self.assertEqual(self.ids(), [self.a1, self.a2])

    def test_all_starred_and_most_relevant(self):
        self.assertEqual(self.ids(filter="all"), [self.a1, self.a4, self.a2, self.a3])
        self.assertEqual(self.ids(filter="starred"), [self.a2])
        self.assertEqual(self.ids(sort="relevant")[0], self.a2)

    def test_counts_and_paging(self):
        body = c.get("/api/articles", params={"filter": "all", "limit": 2, "offset": 1}).json()
        self.assertEqual([a["id"] for a in body["items"]], [self.a4, self.a2])
        self.assertEqual((body["total"], body["counts"]["total"], body["counts"]["starred"]), (4, 4, 1))

    def test_articles_of_a_removed_source_disappear(self):
        c.delete(f"/api/sources/{self.src}")
        self.assertEqual(self.ids(filter="all"), [])

    def test_star_and_read_are_saved(self):
        c.patch(f"/api/articles/{self.a1}", json={"starred": True, "read": True})
        a = c.get(f"/api/articles/{self.a1}").json()
        self.assertTrue(a["starred"] and a["read"])
        c.patch(f"/api/articles/{self.a1}", json={"starred": False})
        self.assertFalse(c.get(f"/api/articles/{self.a1}").json()["starred"])

    def test_one_article_has_text_and_summary_keys(self):
        a = c.get(f"/api/articles/{self.a1}").json()
        self.assertEqual(a["title"], "Speculative decoding explained")
        self.assertIn("draft model", a["text"])
        self.assertIsNone(a["summary"])
        self.assertEqual([k for k, _ in a["summary_keys"]], ["about", "says", "supports", "matters", "remember"])
        self.assertEqual(c.get("/api/articles/99999").status_code, 404)

    def test_keyword_search_finds_the_right_article(self):
        body = c.get("/api/articles", params={"q": "speculative"}).json()
        self.assertTrue(body["search"])
        self.assertEqual([a["id"] for a in body["items"]], [self.a1])
        self.assertEqual(c.get("/api/articles", params={"q": "zzzznothing"}).json()["items"], [])

    def test_search_survives_quotes_and_punctuation(self):
        for q in ['"', "a\"b", "kernels OR", "SWE-bench", "(", "***"]:
            with self.subTest(q=q):
                self.assertEqual(c.get("/api/articles", params={"q": q}).status_code, 200)

    def test_sharing_refuses_local_and_non_web_addresses(self):
        for url in ["http://127.0.0.1:8000/x", "http://localhost/x", "file:///etc/passwd", "ftp://example.com/x", "http://user:pw@example.com/"]:
            with self.subTest(url=url):
                self.assertEqual(c.post("/api/share", json={"url": url}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
