import gzip, json, unittest
from sw import graph
from tests import helpers as h

c = h.client


def seed():
    src = h.add_source("Blog")
    public = h.add_article(src, "Public post", "Public text about inference.")
    secret = h.add_article(src, "Private repo doc", "Secret internal text.", private=1)
    t_pub, t_priv = graph.resolve("Inference", "concept"), graph.resolve("Internal tool", "tool")
    h.db.x("INSERT INTO mentions(article_id,theme_id,ts) VALUES(?,?,?)", (public, t_pub, 1))
    h.db.x("INSERT INTO mentions(article_id,theme_id,ts) VALUES(?,?,?)", (secret, t_priv, 1))
    h.db.x("INSERT INTO edges(a,b,relation,article_id,ts) VALUES(?,?,?,?,?)", (t_pub, t_priv, "uses", secret, 1))
    h.db.x("INSERT INTO chunks(article_id,idx,text,vec) VALUES(?,?,?,?)", (public, 0, "chunk", b"\x00\x00\x80\x3f"))
    pid = c.post("/api/projects", json={"name": "P", "goal": "G", "brief": "B"}).json()["id"]
    c.post(f"/api/projects/{pid}/items", json={"kind": "decision", "text": "Decide"})
    c.put("/api/settings", json={"values": {"interests": "inference", "github_token": "ghp_x"}})
    return public, secret


class ExportTests(unittest.TestCase):
    def setUp(self): h.reset(); self.public, self.secret = seed()

    def test_json_export_leaves_private_content_out_unless_asked(self):
        plain = c.get("/api/export/json").json()["tables"]
        self.assertEqual([a["title"] for a in plain["articles"]], ["Public post"])
        full = c.get("/api/export/json", params={"include_private": True}).json()["tables"]
        self.assertEqual(len(full["articles"]), 2)
        self.assertNotIn("Secret internal text", c.get("/api/export/json").text)

    def test_graphml_hides_themes_found_only_in_private_content(self):
        xml = c.get("/api/export/graphml").text
        self.assertIn("Inference", xml); self.assertNotIn("Internal tool", xml)
        self.assertIn("Internal tool", c.get("/api/export/graphml", params={"include_private": True}).text)


class BackupTests(unittest.TestCase):
    def setUp(self): h.reset(); seed()

    def counts(self): return {t: h.db.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in h.api.TABLES}

    def test_a_backup_restores_everything_including_private_content(self):
        before = self.counts()
        blob = c.post("/api/backup", json={"passphrase": "correct horse"}).content
        self.assertTrue(blob.startswith(b"SWBK1"))
        self.assertNotIn(b"Public text", blob, "the file is encrypted")
        h.reset()
        self.assertEqual(sum(self.counts().values()), 0)
        r = c.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.counts(), before)
        self.assertEqual(h.db.q("SELECT vec FROM chunks", one=True)["vec"], b"\x00\x00\x80\x3f")
        self.assertEqual(h.db.q("SELECT private FROM articles WHERE title='Private repo doc'", one=True)["private"], 1)
        self.assertEqual(len(c.get("/api/articles", params={"q": "inference"}).json()["items"]), 1, "search works after a restore")
        self.assertEqual(c.get("/api/settings").json()["interests"], "inference")

    def test_the_token_and_lock_are_not_in_a_backup(self):
        h.db.set_setting("api_key", "sk-or-secret"); h.db.set_setting("remote_hash", "salt:hash"); h.db.set_setting("remote_sessions", {"abc": {"created": 1, "last": 1}}); h.db.set_setting("remote_enabled", True)
        blob = c.post("/api/backup", json={"passphrase": "correct horse"}).content
        from sw.tts import db  # noqa: F401  (same db module)
        key = h.api._key("correct horse", blob[5:21])
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        data = json.loads(gzip.decompress(AESGCM(key).decrypt(blob[21:33], blob[33:], b"SWBK1")))
        for secret in ("github_token", "lock_hash", "lock_enabled", "api_key", "remote_hash", "remote_sessions", "remote_log", "remote_enabled", "remote_login"):
            self.assertNotIn(secret, data["settings"])
        self.assertNotIn("sk-or-secret", json.dumps(data)); self.assertNotIn("salt:hash", json.dumps(data))

    def test_domains_and_developments_travel_with_a_backup(self):
        from sw import signals
        signals.domains(); sid = h.add_source("S"); aid = h.add_article(sid, "vLLM", "x" * 600)
        h.db.x("INSERT INTO developments(article_id,kind,claim,evidence,grounded,ts,created,model,domains) VALUES(?,?,?,?,?,?,?,?,?)", (aid, "efficiency", "Faster.", "measured", 1, 1.0, 1.0, "m", "[]"))
        h.db.x("INSERT INTO development_runs(article_id,ts,status,model,n) VALUES(?,?,?,?,?)", (aid, 1.0, "ok", "m", 1))
        before = self.counts()
        blob = c.post("/api/backup", json={"passphrase": "correct horse"}).content; h.reset()
        r = c.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(r.status_code, 200)
        self.assertEqual(h.db.q("SELECT COUNT(*) n FROM developments", one=True)["n"], 1); self.assertEqual(h.db.q("SELECT COUNT(*) n FROM development_runs", one=True)["n"], 1)
        self.assertGreaterEqual(h.db.q("SELECT COUNT(*) n FROM domains", one=True)["n"], 5)

    def test_a_wrong_passphrase_or_damaged_file_changes_nothing(self):
        before = self.counts()
        blob = c.post("/api/backup", json={"passphrase": "correct horse"}).content
        for body, phrase in [(blob, "wrong passphrase"), (blob[:-5], "correct horse"), (b"SWBK1" + b"x" * 60, "correct horse")]:
            r = c.post("/api/restore", content=body, headers={"x-passphrase": phrase})
            self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(c.post("/api/restore", content=b"not a backup", headers={"x-passphrase": "x"}).status_code, 400)
        self.assertEqual(self.counts(), before)

    def test_a_short_passphrase_is_refused(self):
        self.assertEqual(c.post("/api/backup", json={"passphrase": "short"}).status_code, 400)

    def test_erasing_needs_the_confirmation_word(self):
        self.assertEqual(c.post("/api/danger/erase", json={}).status_code, 400)
        self.assertGreater(sum(self.counts().values()), 0)
        self.assertEqual(c.post("/api/danger/erase", json={"confirm": "erase"}).status_code, 200)
        self.assertEqual(sum(self.counts().values()), 0)
        self.assertEqual(c.get("/api/articles", params={"q": "inference"}).json()["items"], [])


if __name__ == "__main__":
    unittest.main()
