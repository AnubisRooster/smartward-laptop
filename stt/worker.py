"""Turns audio files into text on request, for the phone. One JSON line in, one JSON line out; run by the SmartWard API.

  in:  {"id": 7, "path": "/tmp/clip.wav"}
  out: {"id": 7, "text": "...", "ms": 612}   or   {"id": 7, "error": "..."}
Nothing is kept: the API deletes the file as soon as it has the text. Quits when stdin closes."""
import json, sys, time
from listen import clean            # the same "is this real speech?" filter the laptop microphone uses


def main():
    name = sys.argv[1]
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=4)
    except Exception as e:
        print(json.dumps({"id": 0, "error": f"Couldn't load the speech model: {e}"}), flush=True); return 1
    print(json.dumps({"id": 0, "ready": True}), flush=True)
    for line in sys.stdin:
        try: req = json.loads(line)
        except ValueError: continue
        t0 = time.time()
        try:
            segs, info = model.transcribe(req["path"], language="en" if name.endswith(".en") else None, beam_size=1, condition_on_previous_text=False, vad_filter=False)
            segs = list(segs); text = clean(" ".join(s.text for s in segs), info.duration, segs)
            print(json.dumps({"id": req["id"], "text": text, "ms": int((time.time() - t0) * 1000)}), flush=True)
        except Exception as e:
            print(json.dumps({"id": req.get("id"), "error": f"{type(e).__name__}: {e}"[:200]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
