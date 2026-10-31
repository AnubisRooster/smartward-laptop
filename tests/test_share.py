import time, unittest
from unittest import mock
from sw import db, implications as im, memo, share
from tests import helpers as h
from tests.test_implications import dev, hyp, project, reply
from tests.test_memo import Setup as MemoSetup

c = h.client
NOW = time.time()


class Sharing(MemoSetup):
    def make_memo(self, **kw):
        with mock.patch("litellm.completion", return_value=self.memo_reply(**kw)): return memo.generate(NOW)

    def make_hyps(self):
        with mock.patch("litellm.completion", return_value=reply([hyp([self.ids[0], self.ids[1]]), hyp([self.ids[2]], headline="Another idea entirely about decode", direction="threatens")])): im.generate(self.pid)
        return [r["id"] for r in db.q("SELECT id FROM hypotheses ORDER BY id")]

    def test_a_memo_becomes_confluence_storage_html_and_markdown_with_numbered_sources(self):
        m = self.make_memo()
        conf = share.render("memo", m["id"], "confluence")["content"]
        self.assertIn("<h1>Strategy memo — week", conf); self.assertIn("<h2>What shifted</h2>", conf); self.assertIn("<sup>[1]</sup>", conf); self.assertIn("<h2>Sources</h2>", conf)
        md = share.render("memo", m["id"], "markdown"); self.assertTrue(md["filename"].endswith(".md")); self.assertIn("## What to watch next week", md["content"]); self.assertIn("1. [Story", md["content"])
        html = share.render("memo", m["id"], "html")["content"]; self.assertIn('href="#src-1"', html)

    def test_the_same_article_is_one_source_however_often_it_is_cited(self):
        m = self.make_memo(); d = share.memo_doc(m["id"])
        self.assertEqual(len(d.sources), len({s["url"] for s in d.sources}))

    def test_a_project_share_has_its_hypotheses_with_badges_and_leaves_out_dismissed_ones(self):
        a, b = self.make_hyps(); im.accept(a); im.dismiss(b, "no")
        out = share.render("project", self.pid, "confluence")["content"]
        self.assertIn('ac:name="status"', out); self.assertIn("Accepted", out); self.assertNotIn("Another idea entirely", out); self.assertIn("What would change our mind", out)

    def test_a_project_with_private_links_is_refused_and_private_citations_are_left_out(self):
        self.make_hyps(); db.x("UPDATE articles SET private=1 WHERE id=(SELECT article_id FROM developments WHERE id=?)", (self.ids[1],))
        r = share.render("project", self.pid, "markdown"); self.assertEqual(r["left_out"], 1); self.assertIn("1 private citation was left out", r["content"].replace("\\", ""))
        db.x("INSERT INTO project_links(project_id,kind,url,private) VALUES(?,?,?,1)", (self.pid, "github", "https://github.com/me/secret"))
        with self.assertRaises(share.Refused): share.render("project", self.pid)
        self.assertEqual(c.get(f"/api/export/share/project/{self.pid}").status_code, 403)

    def test_page_text_cannot_inject_markup(self):
        self.make_hyps(); db.x("UPDATE hypotheses SET headline=?, implication=?", ("<script>alert(1)</script>", "**bold** [x](javascript:alert(1))"))
        db.x("UPDATE articles SET url='javascript:alert(' || id || ')'")
        html = share.render("project", self.pid, "html")["content"]; self.assertNotIn("<script>", html); self.assertNotIn('href="javascript', html)
        md = share.render("project", self.pid, "markdown")["content"]; self.assertIn("\\[x\\](javascript", md); self.assertNotIn("](<javascript", md); self.assertIn("\\*\\*bold\\*\\*", md)      # escaped: shows as text, never a link

    def test_api_errors_and_phone_access(self):
        m = self.make_memo()
        self.assertEqual(c.get(f"/api/export/share/memo/{m['id']}?format=markdown").json()["format"], "markdown")
        self.assertEqual(c.get("/api/export/share/memo/999").status_code, 404); self.assertEqual(c.get(f"/api/export/share/memo/{m['id']}?format=pdf").status_code, 400)
        self.assertEqual(c.get(f"/api/export/share/project/{self.pid}").status_code, 404)                 # nothing to share yet
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in(); self.assertEqual(c.get(f"/api/export/share/memo/{m['id']}", headers=VIA).status_code, 200)

    def test_a_download_is_a_file_with_a_sensible_name(self):
        m = self.make_memo(); r = c.get(f"/api/export/share/memo/{m['id']}?format=html&download=true")
        self.assertIn("attachment", r.headers["content-disposition"]); self.assertIn("strategy-memo-week", r.headers["content-disposition"]); self.assertTrue(r.text.startswith("<!doctype html>"))
        self.assertTrue(c.get(f"/api/export/share/memo/{m['id']}?format=confluence&download=true").headers["content-type"].startswith("application/xml"))

    def test_implications_never_draw_on_private_articles(self):
        secret = h.add_article(self.src, "Private notes", "x" * 600, private=1); dev(secret, claim="Secret claim.")
        g = im.gather(db.q("SELECT * FROM projects", one=True), NOW); self.assertNotIn("Secret claim.", [r["claim"] for r in g["evidence"]])


if __name__ == "__main__":
    unittest.main()
