import os, sys, time, unittest
import numpy as np
from sw import stt
from tests import helpers as h

c = h.client
FAKE = os.path.join(os.path.dirname(__file__), "fixtures", "fake_listener.py")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "stt"))
from vad import Endpointer, FRAME   # noqa: E402


def wait(pred, secs=5):
    end = time.time() + secs
    while time.time() < end:
        if pred(): return True
        time.sleep(0.05)
    return False


class ListenerTests(unittest.TestCase):
    def setUp(self): os.environ["SMARTWARD_STT_CMD"] = f"{sys.executable} {FAKE}"; stt.reset()
    def tearDown(self): stt.reset(); os.environ.pop("SMARTWARD_STT_CMD", None)

    def test_start_delivers_events_in_order_and_only_once(self):
        self.assertEqual(c.post("/api/voice/start").status_code, 200)
        self.assertTrue(wait(lambda: len(c.get("/api/voice/poll").json()["events"]) >= 2))
        body = c.get("/api/voice/poll").json()
        self.assertEqual([e["type"] for e in body["events"]], ["ready", "text"]); self.assertEqual(body["events"][1]["text"], "hello strategist")
        self.assertTrue(body["ready"]); self.assertTrue(body["running"])
        self.assertEqual(c.get("/api/voice/poll", params={"after": body["seq"]}).json()["events"], [])

    def test_pause_and_resume_reach_the_listener(self):
        c.post("/api/voice/start"); wait(lambda: c.get("/api/voice/poll").json()["ready"])
        self.assertTrue(c.post("/api/voice/pause").json()["ok"])
        self.assertTrue(wait(lambda: c.get("/api/voice/poll").json()["state"] == "paused"))

    def test_stop_closes_the_microphone(self):
        c.post("/api/voice/start"); wait(lambda: c.get("/api/voice/poll").json()["running"])
        self.assertFalse(c.post("/api/voice/stop").json()["running"])
        self.assertFalse(c.post("/api/voice/pause").json()["ok"])

    def test_it_closes_itself_when_nobody_is_asking(self):
        old = stt.IDLE_STOP_S; stt.IDLE_STOP_S = 1
        try:
            c.post("/api/voice/start"); self.assertTrue(wait(lambda: c.get("/api/voice/poll").json()["running"]))
            self.assertTrue(wait(lambda: not stt.status()["running"], 5))
        finally: stt.IDLE_STOP_S = old

    def test_not_installed_is_a_clear_409(self):
        os.environ.pop("SMARTWARD_STT_CMD"); stt.reset()
        if not stt.installed():
            r = c.post("/api/voice/start"); self.assertEqual(r.status_code, 409); self.assertIn("setup.sh", r.json()["detail"])


def frames(seconds, level):
    n = int(seconds * 50)
    return [(np.random.randn(FRAME) * level).astype(np.int16) for _ in range(n)]


def run(ep, frs):
    ev = []
    for f in frs:
        e = ep.feed(f)
        if e: ev.append(e)
    return ev


class EndpointerTests(unittest.TestCase):
    def test_a_sentence_between_silences_is_one_utterance(self):
        ep = Endpointer(); ev = run(ep, frames(2, 8) + frames(1.5, 3000) + frames(2, 8))
        self.assertEqual([e[0] for e in ev], ["start", "end"])
        secs = len(ev[1][1]) / 16000; self.assertTrue(1.5 < secs < 2.8, secs)       # speech + preroll + the trailing silence that ended it

    def test_silence_and_room_noise_never_start(self):
        self.assertEqual(run(Endpointer(), frames(10, 8)), []); self.assertEqual(run(Endpointer(), frames(10, 40)), [])

    def test_a_click_is_dropped(self):
        ev = run(Endpointer(), frames(2, 8) + frames(0.1, 3000) + frames(2, 8))
        self.assertTrue(all(e[1] is None for e in ev if e[0] == "end"))

    def test_a_pause_inside_a_sentence_does_not_split_it(self):
        ev = run(Endpointer(), frames(2, 8) + frames(1, 3000) + frames(0.4, 8) + frames(1, 3000) + frames(2, 8))
        self.assertEqual([e[0] for e in ev], ["start", "end"])

    def test_two_sentences_are_two_utterances(self):
        ev = run(Endpointer(), frames(2, 8) + frames(1, 3000) + frames(1.5, 8) + frames(1, 3000) + frames(1.5, 8))
        self.assertEqual([e[0] for e in ev], ["start", "end", "start", "end"])

    def test_it_adapts_to_a_noisy_room(self):
        ep = Endpointer(); ev = run(ep, frames(3, 150) + frames(1.5, 4000) + frames(2, 150))
        self.assertEqual([e[0] for e in ev], ["start", "end"])


if __name__ == "__main__":
    unittest.main()


FAKE_WORKER = os.path.join(os.path.dirname(__file__), "fixtures", "fake_worker.py")


class TranscribeTests(unittest.TestCase):
    def setUp(self): os.environ["SMARTWARD_STT_CMD"] = "x"; os.environ["SMARTWARD_STT_WORKER_CMD"] = f"{sys.executable} {FAKE_WORKER}"; stt.reset()
    def tearDown(self): stt.reset(); os.environ.pop("SMARTWARD_STT_CMD", None); os.environ.pop("SMARTWARD_STT_WORKER_CMD", None)

    def post(self, data, kind="audio/wav"): return c.post("/api/voice/transcribe", content=data, headers={"Content-Type": kind})

    def test_a_recording_becomes_text(self):
        r = self.post(b"RIFF" + b"0" * 100); self.assertEqual(r.status_code, 200); self.assertEqual(r.json()["text"], "heard 104 bytes as .wav")

    def test_phone_formats_are_accepted_and_keep_their_extension(self):
        self.assertTrue(self.post(b"x" * 10, "audio/webm;codecs=opus").json()["text"].endswith(".webm"))
        self.assertTrue(self.post(b"x" * 10, "audio/mp4").json()["text"].endswith(".mp4"))

    def test_the_worker_is_reused_between_recordings(self):
        self.post(b"a" * 5); first = stt._w["proc"]; self.post(b"a" * 6); self.assertIs(stt._w["proc"], first)

    def test_bad_requests_are_refused_plainly(self):
        self.assertEqual(self.post(b"").status_code, 400); self.assertEqual(self.post(b"x", "text/plain").status_code, 415)
        self.assertEqual(self.post(b"x" * (stt.MAX_AUDIO_BYTES + 1)).status_code, 413)

    def test_nothing_is_left_on_disk(self):
        import glob, tempfile
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "tmp*.wav"))); self.post(b"x" * 9)
        self.assertEqual(set(glob.glob(os.path.join(tempfile.gettempdir(), "tmp*.wav"))), before)

    def test_a_phone_with_a_session_may_use_it_and_the_laptop_microphone_stays_blocked(self):
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.post("/api/voice/transcribe", content=b"x" * 8, headers={**VIA, "Content-Type": "audio/wav"}).status_code, 200)
        self.assertEqual(c.post("/api/voice/start", headers=VIA).status_code, 403)

    def test_an_unavailable_model_is_a_503_with_the_fix(self):
        os.environ.pop("SMARTWARD_STT_CMD"); stt.reset()
        if not stt.installed(): r = self.post(b"x"); self.assertEqual(r.status_code, 503); self.assertIn("setup.sh", r.json()["detail"])
