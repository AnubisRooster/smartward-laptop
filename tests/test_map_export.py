import base64, os, tempfile, unittest
import xml.etree.ElementTree as ET
from unittest import mock
from sw import mapexport, maps
from tests import helpers as h
from tests.test_implications import project
from tests.test_rules import GOOD

c = h.client


class Export(unittest.TestCase):
    def setUp(self):
        h.reset(); self.pid = project(name="AI Platform & Co"); maps.save(self.pid, GOOD + "~Cost meter (service): finops  # suggested by O3\n")

    def test_the_drawio_file_has_every_zone_part_and_arrow(self):
        r = mapexport.export(self.pid, "drawio"); self.assertEqual(r["filename"], "ai-platform-co-architecture.drawio")
        root = ET.fromstring(r["content"]); m = maps.parse(GOOD + "~Cost meter (service): finops  # suggested by O3\n")
        parts = {o.get("id"): o for o in root.iter("object")}
        self.assertEqual({o.get("label") for o in parts.values()}, {p["label"] for p in m["parts"]})
        zones = [x for x in root.iter("mxCell") if (x.get("style") or "").startswith("swimlane")]
        self.assertEqual([z.get("value") for z in zones], m["zones"])
        edges = [x for x in root.iter("mxCell") if x.get("edge") == "1"]; self.assertEqual(len(edges), len(m["edges"]))
        self.assertTrue(all(e.get("source") in parts and e.get("target") in parts for e in edges))
        ctl = next(e for e in edges if e.get("value") == "authenticates"); self.assertIn("dashed=1", ctl.get("style"))
        cost = next(o for o in parts.values() if o.get("label") == "Cost meter")
        self.assertEqual(cost.get("tooltip"), "suggested by O3"); self.assertIn("dashed=1", cost.find("mxCell").get("style"))
        bedrock = next(o for o in parts.values() if o.get("label") == "Bedrock"); self.assertIn("cloud", bedrock.find("mxCell").get("style"))

    def test_parts_sit_inside_their_zone_without_overlapping(self):
        root = ET.fromstring(mapexport.export(self.pid, "drawio")["content"]); boxes = {}
        for o in root.iter("object"):
            cell = o.find("mxCell"); g = cell.find("mxGeometry")
            boxes.setdefault(cell.get("parent"), []).append(tuple(float(g.get(k)) for k in ("x", "y", "width", "height")))
        for bs in boxes.values():
            for i, a in enumerate(bs):
                for b in bs[i + 1:]: self.assertFalse(a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3], (a, b))

    def test_mermaid_is_the_bare_design_and_text_is_the_saved_lines(self):
        md = mapexport.export(self.pid, "mermaid")["content"]
        self.assertTrue(md.startswith("%% AI Platform & Co: architecture\nflowchart TB")); self.assertNotIn("classDef threatens", md)
        self.assertEqual(mapexport.export(self.pid, "text")["content"], maps.get(self.pid)["text"].rstrip() + "\n")

    def test_bad_formats_and_missing_maps_are_refused(self):
        self.assertEqual(c.get(f"/api/projects/{self.pid}/map/export", params={"format": "exe"}).status_code, 400)
        self.assertEqual(c.get(f"/api/projects/{project(name='Empty')}/map/export").status_code, 404)
        r = c.get(f"/api/projects/{self.pid}/map/export", params={"format": "drawio", "download": "true"})
        self.assertIn('filename="ai-platform-co-architecture.drawio"', r.headers["content-disposition"])

    def test_a_phone_can_download_but_not_write_files_on_the_laptop(self):
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get(f"/api/projects/{self.pid}/map/export", params={"format": "mermaid"}, headers=VIA).status_code, 200)
        self.assertEqual(c.post("/api/downloads", json={"filename": "x.txt", "text": "hi"}, headers=VIA).status_code, 403)


class SaveDownload(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); p = mock.patch.object(mapexport, "DOWNLOADS", self.dir); p.start(); self.addCleanup(p.stop)

    def test_files_land_in_downloads_under_an_unused_name(self):
        png = base64.b64encode(b"\x89PNG fake").decode()
        a = c.post("/api/downloads", json={"filename": "map.png", "base64": png}).json()["path"]
        b = c.post("/api/downloads", json={"filename": "map.png", "base64": png}).json()["path"]
        self.assertEqual((os.path.dirname(a), os.path.basename(a), os.path.basename(b)), (self.dir, "map.png", "map (2).png"))
        with open(a, "rb") as f: self.assertEqual(f.read(), b"\x89PNG fake")

    def test_paths_and_unknown_kinds_are_refused(self):
        r = c.post("/api/downloads", json={"filename": "../../.bashrc.txt", "text": "x"}); self.assertEqual(os.path.dirname(r.json()["path"]), self.dir)
        for name in ("evil.sh", "noext", ".txt"):
            self.assertEqual(c.post("/api/downloads", json={"filename": name, "text": "x"}).status_code, 400, name)
        self.assertEqual(c.post("/api/downloads", json={"filename": "a.png", "base64": "not base64!"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
