"""Listens on the microphone and prints what was said, one JSON line per event. Run by the SmartWard API; never opens a network port.

  {"type":"ready"}                      model loaded, listening
  {"type":"state","state":"hearing"}    you started talking   ("listening" when you stop)
  {"type":"text","text":"...","ms":412} one finished utterance
  {"type":"error","message":"..."}

Commands arrive on stdin, one per line: pause (discard audio while SmartWard speaks), resume, quit.
"""
import argparse, json, subprocess, sys, threading, time
import numpy as np
from vad import Endpointer, FRAME

# Whisper tends to invent these from silence or room noise.
PHANTOMS = {"you", "thank you", "thank you.", "thanks for watching", "thanks for watching.", "bye", "bye.", "."}


def out(**kw):
    print(json.dumps(kw), flush=True)


def clean(text, seconds, segments):
    text = " ".join(text.split())
    if not text: return ""
    if segments and (max(s.no_speech_prob for s in segments) > 0.6 or min(s.avg_logprob for s in segments) < -1.2): return ""
    if seconds < 1.5 and text.lower() in PHANTOMS: return ""
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--silence-ms", type=int, default=800); ap.add_argument("--device", default="default"); ap.add_argument("--raw-cmd", default="", help="test hook: a shell command that prints raw 16 kHz mono S16_LE audio instead of the microphone")
    a = ap.parse_args()
    paused = threading.Event(); quit_ = threading.Event(); resumed_at = [0.0]

    def commands():
        for line in sys.stdin:
            c = line.strip()
            if c == "pause": paused.set()
            elif c == "resume": resumed_at[0] = time.time(); paused.clear()
            elif c == "quit": break
        quit_.set()
    threading.Thread(target=commands, daemon=True).start()

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=4)
    except Exception as e:
        out(type="error", message=f"Couldn't load the speech model: {e}"); return 1
    cmd = ["arecord", "-q", "-D", a.device, "-t", "raw", "-f", "S16_LE", "-r", "16000", "-c", "1"]
    try: rec = subprocess.Popen(a.raw_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) if a.raw_cmd else subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        out(type="error", message="arecord isn't installed (Ubuntu: sudo apt install alsa-utils)."); return 1
    ep = Endpointer(silence_ms=a.silence_ms); out(type="ready")
    nbytes = FRAME * 2; heard = False
    while not quit_.is_set():
        buf = rec.stdout.read(nbytes)
        if len(buf) < nbytes:
            err = (rec.stderr.read() or b"").decode(errors="replace").strip()
            out(type="error", message="The microphone stopped: " + (err or "no audio from it.")); return 1
        if paused.is_set() or time.time() - resumed_at[0] < 0.5:      # SmartWard is talking, or just stopped: its own voice isn't input
            if ep.active or heard: ep.reset(); heard = False
            continue
        ev = ep.feed(np.frombuffer(buf, dtype=np.int16))
        if ev is None: continue
        if ev[0] == "start": heard = True; out(type="state", state="hearing"); continue
        heard = False; out(type="state", state="listening")
        audio = ev[1]
        if audio is None: continue
        t0 = time.time()
        segs, _ = model.transcribe(audio, language="en" if a.model.endswith(".en") else None, beam_size=1, condition_on_previous_text=False, vad_filter=False)
        segs = list(segs); text = clean(" ".join(s.text for s in segs), len(audio) / 16000, segs)
        if text: out(type="text", text=text, ms=int((time.time() - t0) * 1000))
    rec.terminate(); return 0


if __name__ == "__main__":
    sys.exit(main())
