import unittest
from tests import helpers as h

c = h.client


class SettingsTests(unittest.TestCase):
    def setUp(self): h.reset()

    def test_defaults_are_there(self):
        s = c.get("/api/settings").json()
        self.assertEqual(s["tts_engine"], "auto")
        self.assertEqual(s["tts_voice"], "af_heart")
        self.assertEqual(s["tts_profiles"], {})
        self.assertEqual(s["voice_rate"], 1.0)
        self.assertTrue(s["private_repo_local_only"])

    def test_values_round_trip(self):
        r = c.put("/api/settings", json={"values": {"voice_rate": 1.25, "interests": "inference, agents", "refresh_minutes": 30}})
        self.assertEqual(r.status_code, 200)
        s = c.get("/api/settings").json()
        self.assertEqual((s["voice_rate"], s["interests"], s["refresh_minutes"]), (1.25, "inference, agents", 30))

    def test_tokens_and_keys_are_never_sent_back(self):
        c.put("/api/settings", json={"values": {"github_token": "ghp_secret", "api_key": "sk-secret"}})
        s = c.get("/api/settings").json()
        self.assertIs(s["github_token"], True)
        self.assertIs(s["api_key"], True)
        self.assertNotIn("secret", c.get("/api/settings").text)
        c.put("/api/settings", json={"values": {"github_token": ""}})
        self.assertIs(c.get("/api/settings").json()["github_token"], False)

    def test_the_lock_hash_cannot_be_set_through_settings(self):
        c.put("/api/settings", json={"values": {"lock_hash": "abc:def"}})
        self.assertIs(c.get("/api/settings").json()["lock_hash"], False)

    def test_bad_speech_settings_are_refused_and_change_nothing(self):
        for key, value in [("tts_url", "http://192.168.1.2:8880"), ("tts_url", "https://api.openai.com"),
                           ("tts_voice", "../etc/passwd"), ("tts_engine", "cloud"), ("voice_rate", 9),
                           ("tts_profiles", {"": {"voice": "af_heart", "rate": 1}}),
                           ("tts_profiles", {"A": {"voice": "af_heart", "rate": 9}}),
                           ("tts_profile", "no such profile")]:
            with self.subTest(key=key, value=value):
                r = c.put("/api/settings", json={"values": {key: value}})
                self.assertEqual(r.status_code, 400, r.text)
        s = c.get("/api/settings").json()
        self.assertEqual((s["tts_url"], s["tts_voice"], s["tts_engine"]), ("http://127.0.0.1:8880", "af_heart", "auto"))

    def test_a_profile_can_be_saved_and_chosen_in_one_request(self):
        profiles = {"Commute": {"voice": "bf_emma", "rate": 1.3}}
        r = c.put("/api/settings", json={"values": {"tts_profiles": profiles, "tts_profile": "Commute"}})
        self.assertEqual(r.status_code, 200, r.text)
        s = c.get("/api/settings").json()
        self.assertEqual((s["tts_profiles"], s["tts_profile"]), (profiles, "Commute"))


if __name__ == "__main__":
    unittest.main()


class TestsNeverTouchARealLibrary(unittest.TestCase):
    """A test run once emptied a real library because a module imported `sw.db` before the temp folder was set."""

    def test_the_library_in_use_is_a_temporary_one(self):
        import os, tempfile
        self.assertTrue(os.path.realpath(h.db.DB_PATH).startswith(os.path.realpath(tempfile.gettempdir())))
        self.assertNotIn(".local/share/smartward", h.db.DB_PATH)

    def test_importing_the_app_modules_first_is_still_safe(self):
        import subprocess, sys
        code = ("import sys; sys.path.insert(0, '.'); import tests.test_projects; from sw import db; "
                "print(db.DB_PATH)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=h.ROOT, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("smartward-test-", out.stdout)


class UiBuildTests(unittest.TestCase):
    def test_status_carries_a_build_number_so_an_open_window_can_offer_to_reload(self):
        h.reset(); self.assertIsInstance(h.client.get("/api/status").json()["ui_build"], int)
