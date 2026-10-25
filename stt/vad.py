"""Finds where you start and stop speaking in a stream of 20 ms microphone frames. Pure numpy, no model, easy to test."""
from collections import deque
import numpy as np

RATE = 16000
FRAME = 320                      # 20 ms of 16 kHz samples


def rms_db(frame):
    x = np.asarray(frame, dtype=np.float32)
    return 20 * np.log10(max(float(np.sqrt(np.mean(x * x))), 1e-9) / 32768.0)


class Endpointer:
    """feed() one frame at a time. Returns ("start", None), ("end", float32 audio) or None.

    Speech is a few frames clearly louder than the room (a floor that tracks the quietest recent sound).
    An utterance ends after `silence_ms` without speech, or at `max_s`. Short bursts (a click, a cough) are dropped.

    A room that gets noisier while you are not talking (a fan, music, a vacuum) would sit above the threshold learned in the quiet, look like
    speech forever, and hold the microphone open until `max_s`. Speech is never flat: its level moves by many dB within two seconds. So when
    two whole seconds are loud and within `flat_db` of each other, that is noise: whatever came before it is kept if it was speech, the noise is dropped, and the room is learned afresh.
    """

    def __init__(self, silence_ms=800, min_speech_ms=300, max_s=30, margin_db=11, floor_min_db=-60, abs_min_db=-48, preroll_ms=300, flat_db=6):
        self.silence_frames = silence_ms // 20; self.min_speech_frames = min_speech_ms // 20; self.max_frames = int(max_s * 50)
        self.margin, self.abs_min = margin_db, abs_min_db
        self.floor = max(floor_min_db, -55.0); self.floor_min = floor_min_db
        self.flat_db = flat_db
        self.recent = deque(maxlen=100)       # the last 2 s of levels, for the floor
        self.levels = deque(maxlen=100)       # the same, while an utterance is open, to tell speech from steady noise
        self.preroll = deque(maxlen=preroll_ms // 20)
        self.reset()

    def reset(self):
        self.active = False; self.audio = []; self.quiet = 0; self.loud_run = 0; self.speech_frames = 0; self.preroll.clear(); self.levels.clear()

    def threshold(self): return max(self.floor + self.margin, self.abs_min)

    def feed(self, frame):
        db = rms_db(frame); loud = db > self.threshold()
        if not loud and not self.active:                       # only learn the room from sounds that aren't speech
            self.recent.append(db)
            if len(self.recent) >= 25: self.floor = max(self.floor_min, float(np.percentile(self.recent, 20)))
        if not self.active:
            self.preroll.append(np.asarray(frame, dtype=np.float32))
            self.loud_run = self.loud_run + 1 if loud else 0
            if self.loud_run >= 3:
                self.active = True; self.audio = list(self.preroll); self.quiet = 0; self.speech_frames = self.loud_run
                return ("start", None)
            return None
        self.audio.append(np.asarray(frame, dtype=np.float32)); self.levels.append(db)
        if loud and len(self.levels) == self.levels.maxlen and max(self.levels) - min(self.levels) < self.flat_db:      # steady, not speech
            n = self.levels.maxlen; before = self.audio[:-n]; enough = self.speech_frames - n >= self.min_speech_frames      # what came before the noise may be real speech
            self.floor = max(self.floor_min, float(np.mean(self.levels))); self.recent.clear(); self.reset()
            return ("end", np.concatenate(before).astype(np.float32) / 32768.0 if enough and before else None)
        if loud: self.quiet = 0; self.speech_frames += 1
        else: self.quiet += 1
        if self.quiet >= self.silence_frames or len(self.audio) >= self.max_frames:
            audio = np.concatenate(self.audio) / 32768.0; enough = self.speech_frames >= self.min_speech_frames
            self.reset()
            return ("end", audio.astype(np.float32) if enough else None)
        return None
