import unittest
from sw import projects
from tests import helpers as h

c = h.client


class ProjectTests(unittest.TestCase):
    def setUp(self):
        h.reset()
        self.pid = c.post("/api/projects", json={"name": "Inference stack", "goal": "Serve models fast", "brief": "v1"}).json()["id"]

    def get(self): return c.get(f"/api/projects/{self.pid}").json()

    def test_create_list_and_get(self):
        row = c.get("/api/projects").json()[0]
        self.assertEqual((row["name"], row["open_items"], row["has_suggestion"]), ("Inference stack", 0, False))
        p = self.get()
        self.assertEqual((p["goal"], p["brief"], p["items"], p["links"]), ("Serve models fast", "v1", [], []))
        self.assertEqual(c.get("/api/projects/9999").status_code, 404)

    def test_editing_the_brief_keeps_history_and_can_be_restored(self):
        c.put(f"/api/projects/{self.pid}", json={"brief": "v2"})
        c.put(f"/api/projects/{self.pid}", json={"brief": "v2"})          # unchanged: no new history
        c.put(f"/api/projects/{self.pid}", json={"brief": "v3", "name": "Renamed"})
        p = self.get()
        self.assertEqual((p["brief"], p["name"], len(p["history"])), ("v3", "Renamed", 2))
        oldest = min(p["history"], key=lambda x: x["id"])
        c.post(f"/api/projects/{self.pid}/restore/{oldest['id']}")
        self.assertEqual(self.get()["brief"], "v1")

    def test_a_suggested_update_shows_a_diff_and_can_be_accepted_or_rejected(self):
        projects.propose(self.pid, "v1\nand more", "Reflects a decision")
        s = self.get()["suggestion"]
        self.assertEqual((s["added"], s["removed"], s["reason"]), (1, 0, "Reflects a decision"))
        self.assertTrue(c.get("/api/projects").json()[0]["has_suggestion"])
        c.post(f"/api/projects/{self.pid}/suggestion/reject")
        self.assertIsNone(self.get()["suggestion"]); self.assertEqual(self.get()["brief"], "v1")
        projects.propose(self.pid, "v1\nand more", "Again")
        c.post(f"/api/projects/{self.pid}/suggestion/accept")
        p = self.get()
        self.assertEqual((p["brief"], p["suggestion"]), ("v1\nand more", None))
        self.assertIn("Accepted suggestion", p["history"][0]["note"])

    def test_items_can_be_added_checked_edited_and_deleted(self):
        iid = c.post(f"/api/projects/{self.pid}/items", json={"kind": "decision", "text": "Use vLLM"}).json()["id"]
        c.post(f"/api/projects/{self.pid}/items", json={"kind": "question", "text": "Which GPU?"})
        self.assertEqual(c.get("/api/projects").json()[0]["open_items"], 2)
        c.patch(f"/api/items/{iid}", json={"done": True, "text": "Use vLLM 0.6"})
        items = {i["id"]: i for i in self.get()["items"]}
        self.assertEqual((items[iid]["done"], items[iid]["text"]), (1, "Use vLLM 0.6"))
        self.assertEqual(c.get("/api/projects").json()[0]["open_items"], 1)
        c.delete(f"/api/items/{iid}")
        self.assertEqual(len(self.get()["items"]), 1)

    def test_links_validate_their_address(self):
        r = c.post(f"/api/projects/{self.pid}/links", json={"url": "http://127.0.0.1:8000"})
        self.assertEqual(r.status_code, 400)
        lid = c.post(f"/api/projects/{self.pid}/links", json={"url": "https://github.com/vllm-project/vllm"}).json()["id"]
        self.assertEqual(self.get()["links"][0]["kind"], "github")
        c.put(f"/api/links/{lid}", json={"url": "https://example.com/docs"})
        self.assertEqual(self.get()["links"][0]["kind"], "url")
        c.delete(f"/api/links/{lid}")
        self.assertEqual(self.get()["links"], [])

    def test_deleting_a_project_removes_what_belongs_to_it(self):
        c.post(f"/api/projects/{self.pid}/items", json={"kind": "action", "text": "Do it"})
        c.post(f"/api/projects/{self.pid}/links", json={"url": "https://github.com/a/b"})
        c.put(f"/api/projects/{self.pid}", json={"brief": "changed"})
        c.delete(f"/api/projects/{self.pid}")
        for table in ("items", "project_links", "brief_history", "projects"):
            self.assertEqual(h.db.q(f"SELECT COUNT(*) n FROM {table}", one=True)["n"], 0, table)

    def test_the_markdown_export_lists_projects_items_and_history(self):
        c.post(f"/api/projects/{self.pid}/items", json={"kind": "decision", "text": "Use vLLM"})
        c.put(f"/api/projects/{self.pid}", json={"brief": "v2"})
        md = c.get("/api/export/markdown").text
        for expected in ("# Inference stack", "**Goal:** Serve models fast", "## Decisions", "- [ ] Use vLLM", "## Brief history"):
            self.assertIn(expected, md)


if __name__ == "__main__":
    unittest.main()
