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
