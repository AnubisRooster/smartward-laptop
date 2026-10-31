import unittest
from unittest import mock
from sw import db, sources
from tests import helpers as h

c = h.client
EVIL = {"Origin": "https://evil.example.com"}


class OtherWebsites(unittest.TestCase):
    def setUp(self): h.reset(); self.sid = h.add_source("vLLM releases", kind="github")

    def test_a_page_on_another_site_cannot_read_or_change_anything(self):
        self.assertEqual(c.delete(f"/api/sources/{self.sid}", headers=EVIL).status_code, 403)
        self.assertEqual(c.get("/api/export/json", headers=EVIL).status_code, 403)
        self.assertEqual(c.put("/api/settings", json={"values": {"model": "x"}}, headers=EVIL).status_code, 403)
        self.assertEqual(c.get("/api/sources", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)     # a plain <img> or link: no Origin, but marked cross-site
        self.assertEqual(c.post("/api/refresh", headers={"Origin": "null"}).status_code, 403)
        self.assertTrue(db.q("SELECT 1 FROM sources WHERE id=?", (self.sid,), one=True))

    def test_the_app_itself_still_works(self):
        for origin in ("http://127.0.0.1:8000", "http://localhost:8000", "tauri://localhost", "http://localhost:1420"):
            self.assertEqual(c.get("/api/sources", headers={"Origin": origin}).status_code, 200, origin)
        self.assertEqual(c.get("/api/sources", headers={"Sec-Fetch-Site": "same-origin"}).status_code, 200)
        self.assertEqual(c.get("/api/status").status_code, 200)                                        # curl and scripts send no Origin
        self.assertEqual(c.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code in (200, 404), True)   # the page itself can still be opened from a link

    def test_cors_only_answers_the_apps_own_origins(self):
        pre = lambda o: c.options("/api/sources", headers={"Origin": o, "Access-Control-Request-Method": "DELETE"})
        self.assertNotIn("access-control-allow-origin", pre("https://evil.example.com").headers)
        self.assertEqual(pre("http://127.0.0.1:8000").headers.get("access-control-allow-origin"), "http://127.0.0.1:8000")

    def test_the_add_to_smartward_bookmarklet_still_works_from_any_page(self):
        r = c.options("/api/share", headers={**EVIL, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(r.status_code, 204); self.assertEqual(r.headers["access-control-allow-origin"], "*")
        with mock.patch("sw.sources.add_page_as_article", return_value=(7, "")):
            r = c.post("/api/share", json={"url": "https://example.com/post"}, headers=EVIL)
        self.assertEqual(r.status_code, 200); self.assertEqual(r.headers["access-control-allow-origin"], "*")


class RemovedSources(unittest.TestCase):
    def setUp(self):
        h.reset(); self.sid = h.add_source("vLLM releases", kind="github", query="vllm-project/vllm")
        self.arts = [h.add_article(self.sid, f"v0.{i}", "notes") for i in range(3)]

    def test_removing_is_recorded_with_where_it_came_from_and_can_be_undone(self):
        c.delete(f"/api/sources/{self.sid}", headers={"Origin": "http://127.0.0.1:8000", "User-Agent": "SmartWard window"})
        self.assertIsNone(db.q("SELECT 1 FROM sources WHERE id=?", (self.sid,), one=True))
        r = c.get("/api/sources/removed").json()["removed"][0]
        self.assertEqual((r["name"], r["articles"]), ("vLLM releases", 3)); self.assertIn("this laptop · http://127.0.0.1:8000 · SmartWard window", r["via"])
        self.assertEqual(c.post(f"/api/sources/removed/{r['id']}/restore").json()["id"], self.sid)
        s = db.q("SELECT * FROM sources WHERE id=?", (self.sid,), one=True); self.assertEqual((s["kind"], s["query"]), ("github", "vllm-project/vllm"))
        self.assertEqual(db.q("SELECT COUNT(*) n FROM articles WHERE source_id=?", (self.sid,), one=True)["n"], 3)
        self.assertEqual(c.post(f"/api/sources/removed/{r['id']}/restore").status_code, 409)
        self.assertEqual(c.post("/api/sources/removed/999/restore").status_code, 404)
        self.assertIn("removed_sources", h.api.TABLES)

    def test_a_new_source_that_fails_takes_what_it_saved_with_it(self):
        def half(sid):
            db.x("INSERT INTO articles(source_id,url,title,created,stage) VALUES(?,?,?,?, 'new')", (sid, "https://example.com/half", "Half", db.now()))
            db.x("UPDATE sources SET last_status='error', last_error='boom' WHERE id=?", (sid,))
        with mock.patch("sw.sources.refresh_source", side_effect=half), self.assertRaises(sources.FetchError):
            sources.add_source("rss", url="https://example.com/feed.xml")
        self.assertIsNone(db.q("SELECT 1 FROM articles WHERE url='https://example.com/half'", one=True))


if __name__ == "__main__":
    unittest.main()
