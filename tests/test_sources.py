import unittest
from sw import pipeline, sources
from tests import helpers as h

c = h.client

RSS = """<?xml version="1.0"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>A blog</title>
<item><title>First post</title><link>https://example.com/1</link><pubDate>Tue, 21 Oct 2025 10:00:00 GMT</pubDate>
<dc:creator>Ada</dc:creator><description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;script&gt;steal()&lt;/script&gt;&lt;/p&gt;</description></item>
<item><title>No link here</title></item></channel></rss>"""
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title><entry><title>Entry one</title>
<link rel="alternate" href="https://example.com/a"/><updated>2025-10-21T10:00:00Z</updated><author><name>Bo</name></author>
<summary>Short summary</summary></entry></feed>"""


class SourceApiTests(unittest.TestCase):
    def setUp(self): h.reset()

    def test_adding_a_source_with_bad_input_says_why(self):
        cases = [({"kind": "rss"}, "Enter a link"), ({"kind": "arxiv"}, "Enter a search"),
                 ({"kind": "github", "query": "not a repo"}, "owner/repo"),
                 ({"kind": "rss", "url": "http://127.0.0.1/feed"}, "private network"),
                 ({"kind": "rss", "url": "file:///etc/passwd"}, "http")]
        for body, words in cases:
            with self.subTest(body=body):
                r = c.post("/api/sources", json=body)
                self.assertEqual(r.status_code, 400, r.text)
                self.assertIn(words, r.json()["detail"])
        self.assertEqual(c.get("/api/sources").json(), [])

    def test_list_rename_disable_and_delete(self):
        sid = h.add_source("Old name")
        h.add_article(sid, "One", "text")
        row = c.get("/api/sources").json()[0]
        self.assertEqual((row["name"], row["n"]), ("Old name", 1))
        c.patch(f"/api/sources/{sid}", json={"name": "New name", "enabled": 0})
        row = c.get("/api/sources").json()[0]
        self.assertEqual((row["name"], row["enabled"]), ("New name", 0))
        c.delete(f"/api/sources/{sid}")
        self.assertEqual(c.get("/api/sources").json(), [])

    def test_feed_discovery_refuses_private_addresses(self):
        self.assertEqual(c.post("/api/discover", json={"url": "http://127.0.0.1/"}).status_code, 400)


class SourceHelperTests(unittest.TestCase):
    def test_canonical_urls_drop_tracking_fragments_and_trailing_slashes(self):
        self.assertEqual(sources.canon("HTTPS://Example.com/Post/?utm_source=x&id=7&fbclid=y#top"), "https://example.com/Post?id=7")
        self.assertEqual(sources.canon("https://example.com"), "https://example.com/")

    def test_unsafe_addresses_are_refused(self):
        for url in ["ftp://example.com", "http://user:pw@example.com", "http://localhost/", "http://127.0.0.1/", "http://10.0.0.5/",
                    "http://169.254.169.254/latest/meta-data", "http://metadata.google.internal/", "http://printer.local/", "http://[::1]/"]:
            with self.subTest(url=url), self.assertRaises(sources.FetchError):
                sources.safe_url(url)

    def test_rss_and_atom_feeds_are_parsed_and_hidden_text_is_dropped(self):
        items = sources.parse_feed(RSS.encode())
        self.assertEqual(len(items), 1, "an item without a link is skipped")
        self.assertEqual((items[0]["title"], items[0]["url"], items[0]["author"]), ("First post", "https://example.com/1", "Ada"))
        self.assertIn("Hello world", items[0]["teaser"]); self.assertNotIn("steal", items[0]["teaser"])
        self.assertIsNotNone(items[0]["published"])
        atom = sources.parse_feed(ATOM.encode())
        self.assertEqual((atom[0]["title"], atom[0]["url"], atom[0]["teaser"]), ("Entry one", "https://example.com/a", "Short summary"))

    def test_html_cleaning_drops_scripts_and_visually_hidden_text(self):
        html = '<p>Visible</p><script>bad()</script><p style="display:none">secret</p><span aria-hidden="true">hidden</span><p hidden>nope</p> tail'
        text = sources.clean_html(html)
        self.assertIn("Visible", text); self.assertIn("tail", text)
        for gone in ("bad()", "secret", "hidden", "nope"):
            self.assertNotIn(gone, text)

    def test_text_is_chunked_with_overlap_and_a_limit(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(400))
        chunks = pipeline.chunk_text(text)
        self.assertTrue(1 < len(chunks) <= 40)
        self.assertTrue(all(len(x) <= 900 for x in chunks))
        self.assertEqual(pipeline.chunk_text(""), [])


if __name__ == "__main__":
    unittest.main()


class FetchCapTests(unittest.TestCase):
    def setUp(self): h.reset()

    def test_a_huge_archive_brings_in_only_the_newest_posts(self):
        from unittest import mock
        from sw import db, sources
        sid = h.add_source("Big archive")
        arts = [{"url": f"https://example.com/p{i}", "title": f"Post {i}", "published": 1000 + i} for i in range(1300)]
        with mock.patch("sw.sources.fetch_source", return_value=(arts, None, None)):
            added = sources.refresh_source(sid)
        self.assertEqual(added, sources.MAX_PER_FETCH)
        titles = {r["title"] for r in db.q("SELECT title FROM articles WHERE source_id=?", (sid,))}
        self.assertIn("Post 1299", titles); self.assertNotIn("Post 0", titles)

    def test_undated_feeds_keep_their_order(self):
        from sw import sources
        arts = [{"url": f"u{i}", "title": str(i)} for i in range(60)]
        self.assertEqual([a["title"] for a in sources.newest(arts, 3)], ["0", "1", "2"])
