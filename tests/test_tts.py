import unittest
from tests import helpers as h

c = h.client


class SpeechProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.fake = h.FakeSpeechServer()

    @classmethod
    def tearDownClass(cls): cls.fake.close()

    def setUp(self):
        h.reset(); self.fake.requests.clear()
        c.put("/api/settings", json={"values": {"tts_url": self.fake.url}})

    def test_status_lists_the_voices_when_the_server_is_up(self):
        s = c.get("/api/tts/status").json()
        self.assertTrue(s["up"])
        self.assertEqual(s["voices"], ["af_heart", "bf_emma"])

    def test_status_says_down_when_nothing_is_listening(self):
        c.put("/api/settings", json={"values": {"tts_url": "http://127.0.0.1:9"}})
        s = c.get("/api/tts/status").json()
        self.assertFalse(s["up"]); self.assertEqual(s["voices"], [])

    def test_speech_is_proxied_with_the_chosen_voice_and_speed(self):
        r = c.post("/api/tts", json={"text": "Hello there.", "voice": "bf_emma", "speed": 1.3})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "audio/wav")
        self.assertTrue(r.content.startswith(b"RIFF"))
        self.assertEqual(self.fake.requests[-1]["input"], "Hello there.")
        self.assertEqual((self.fake.requests[-1]["voice"], self.fake.requests[-1]["speed"]), ("bf_emma", 1.3))

    def test_the_saved_voice_and_rate_are_the_defaults(self):
        c.put("/api/settings", json={"values": {"tts_voice": "bf_emma", "voice_rate": 0.8}})
        c.post("/api/tts", json={"text": "Defaults."})
        self.assertEqual((self.fake.requests[-1]["voice"], self.fake.requests[-1]["speed"]), ("bf_emma", 0.8))

    def test_bad_requests_are_refused_before_reaching_the_server(self):
        for body in [{"text": ""}, {"text": "   "}, {"text": "x" * 3001}, {"text": "hi", "voice": "../x"},
                     {"text": "hi", "voice": "af_heart", "speed": 5}, {"text": "hi", "voice": "af_heart", "speed": 0.1}]:
            with self.subTest(body=str(body)[:50]):
                self.assertEqual(c.post("/api/tts", json=body).status_code, 400)
        self.assertEqual(self.fake.requests, [])

    def test_a_stopped_server_gives_a_clear_error(self):
        c.put("/api/settings", json={"values": {"tts_url": "http://127.0.0.1:9"}})
        r = c.post("/api/tts", json={"text": "Hello."})
        self.assertEqual(r.status_code, 502)
        self.assertIn("isn't running", r.json()["detail"])

    def test_only_this_computer_is_allowed(self):
        from sw import tts
        for url in ["http://127.0.0.1:8880", "http://localhost:8880", "http://[::1]:8880"]:
            self.assertTrue(tts.is_loopback(url), url)
        for url in ["http://192.168.1.2:8880", "https://api.openai.com", "http://127.0.0.1.evil.com", "", "not a url"]:
            self.assertFalse(tts.is_loopback(url), url)


if __name__ == "__main__":
    unittest.main()
