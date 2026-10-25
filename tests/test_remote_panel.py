import json, os, sys, tempfile, unittest
from sw import awake, db, tailscale
from tests import helpers as h

c = h.client
FAKE_TS = '''#!/bin/sh
case "$1" in
  status) echo '{"BackendState":"Running","Self":{"DNSName":"laptop.tail1234.ts.net.","UserID":42},"User":{"42":{"LoginName":"me@example.com"}}}' ;;
  serve) echo "https://laptop.tail1234.ts.net (tailnet only)\\n|-- / proxy http://127.0.0.1:8000" ;;
esac
'''


class AwakeTests(unittest.TestCase):
    def setUp(self): h.reset(); awake.release(); os.environ["SMARTWARD_INHIBIT_CMD"] = "sleep 300"
    def tearDown(self): awake.release(); os.environ["SMARTWARD_INHIBIT_CMD"] = "true"

    def test_held_only_while_remote_is_on(self):
        self.assertFalse(awake.sync())
        c.put("/api/remote/config", json={"login": "me@example.com", "passphrase": "correct horse battery", "enabled": True}); self.assertTrue(awake.running())
        self.assertTrue(c.get("/api/remote/status").json()["awake_held"])
        c.put("/api/remote/config", json={"enabled": False}); self.assertFalse(awake.running())

    def test_can_be_switched_off_on_its_own(self):
        c.put("/api/remote/config", json={"login": "me@example.com", "passphrase": "correct horse battery", "enabled": True})
        c.put("/api/remote/config", json={"keep_awake": False}); self.assertFalse(awake.running()); self.assertFalse(c.get("/api/remote/status").json()["keep_awake"])
        c.put("/api/remote/config", json={"keep_awake": True}); self.assertTrue(awake.running())

    def test_a_missing_inhibitor_is_not_an_error(self):
        os.environ["SMARTWARD_INHIBIT_CMD"] = "/nonexistent/inhibit"; self.assertFalse(awake.hold())


class TailscaleTests(unittest.TestCase):
    def setUp(self): h.reset()
    def tearDown(self): os.environ["SMARTWARD_TAILSCALE_CMD"] = "/nonexistent/tailscale"

    def test_not_installed(self):
        os.environ["SMARTWARD_TAILSCALE_CMD"] = "/nonexistent/tailscale"; self.assertEqual(tailscale.info(), {"installed": False})
        self.assertEqual(c.get("/api/remote/tailscale").json(), {"installed": False})

    def test_reads_the_address_login_and_whether_it_is_published(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f: f.write(FAKE_TS)
        os.chmod(f.name, 0o755); os.environ["SMARTWARD_TAILSCALE_CMD"] = f.name
        try: d = c.get("/api/remote/tailscale").json()
        finally: os.unlink(f.name)
        self.assertEqual((d["installed"], d["state"], d["dns_name"], d["login"], d["https_url"], d["published"]), (True, "Running", "laptop.tail1234.ts.net", "me@example.com", "https://laptop.tail1234.ts.net", True))

    def test_remote_management_is_not_reachable_from_a_phone(self):
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        for m, p in (("get", "/api/remote/tailscale"), ("get", "/api/remote/status")): self.assertEqual(getattr(c, m)(p, headers=VIA).status_code, 403)
        awake.release()


if __name__ == "__main__":
    unittest.main()
