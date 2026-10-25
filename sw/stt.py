"""Speech input for hands-free chat. Runs stt/listen.py (microphone + Whisper, all on this computer) as a child process,
only while the interface is asking for it, and turns what it prints into events the interface polls for."""
import json, os, subprocess, sys, threading, time
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "stt"
IDLE_STOP_S = 15            # the microphone closes by itself if the interface stops asking (window closed, page crashed)

_lock = threading.Lock()
_proc = None
_events = []                # {"seq", "type", ...}; the interface asks for those after the last seq it saw
_seq = 0
_state = {"ready": False, "state": "off", "error": ""}
_last_poll = 0.0


def model_name():
    f = DIR / "model.txt"
    return f.read_text().strip() if f.exists() else "small.en"


def command():
    """What to run. SMARTWARD_STT_CMD replaces it in tests."""
    if os.environ.get("SMARTWARD_STT_CMD"): return os.environ["SMARTWARD_STT_CMD"].split()
    return [str(DIR / ".venv/bin/python"), str(DIR / "listen.py"), "--model", str(DIR / "models" / model_name())]


def installed():
    if os.environ.get("SMARTWARD_STT_CMD"): return True
    return (DIR / ".venv/bin/python").exists() and (DIR / "models" / model_name() / "model.bin").exists()


def status():
    with _lock:
        return {"installed": installed(), "running": _proc is not None and _proc.poll() is None, "model": model_name(), **_state}


def _push(ev):
    global _seq
    with _lock:
        _seq += 1; _events.append({"seq": _seq, **ev}); del _events[:-200]
        if ev.get("type") == "ready": _state.update(ready=True, state="listening", error="")
        elif ev.get("type") == "state": _state["state"] = ev.get("state", "listening")
        elif ev.get("type") == "error": _state.update(error=ev.get("message", "Something went wrong."), ready=False, state="off")


def _read(proc):
    for line in proc.stdout:
        try: ev = json.loads(line)
        except ValueError: continue
        if isinstance(ev, dict) and ev.get("type") in ("ready", "state", "text", "error"): _push(ev)
    with _lock:
        if _proc is proc: _state.update(ready=False, state="off")


def _watchdog(proc):
    while proc.poll() is None:
        time.sleep(1)
        if time.time() - _last_poll > IDLE_STOP_S: stop(); return


def start():
    global _proc, _last_poll
    if not installed(): raise RuntimeError("Speech input isn't installed. Run stt/setup.sh.")
    with _lock:
        if _proc is not None and _proc.poll() is None: _last_poll = time.time(); return
        _state.update(ready=False, state="loading", error=""); _last_poll = time.time()
        _proc = subprocess.Popen(command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        proc = _proc
    threading.Thread(target=_read, args=(proc,), daemon=True).start()
    threading.Thread(target=_watchdog, args=(proc,), daemon=True).start()


def send(cmd):
    with _lock: proc = _proc
    if proc is None or proc.poll() is not None: return False
    try: proc.stdin.write(cmd + "\n"); proc.stdin.flush(); return True
    except (BrokenPipeError, OSError, ValueError): return False


def stop():
    global _proc
    with _lock: proc, _proc = _proc, None; _state.update(ready=False, state="off")
    if proc is None: return
    try: proc.stdin.write("quit\n"); proc.stdin.flush()
    except (BrokenPipeError, OSError, ValueError): pass
    try: proc.wait(timeout=2)
    except subprocess.TimeoutExpired: proc.kill()
    for f in (proc.stdin, proc.stdout):
        try: f.close()
        except Exception: pass


def poll(after=0):
    global _last_poll
    _last_poll = time.time()
    with _lock: evs = [e for e in _events if e["seq"] > after]
    return {**status(), "events": evs, "seq": _seq}


def reset():
    """Tests: forget everything."""
    global _seq
    stop(); stop_worker()
    with _lock: _events.clear(); _seq = 0; _state.update(ready=False, state="off", error="")


# ---- transcribing a recording sent from a phone ----
WORKER_IDLE_S = 600         # the speech model leaves memory after ten idle minutes
MAX_AUDIO_BYTES = 6_000_000
_w = {"proc": None, "used": 0.0, "id": 0}
_wlock = threading.Lock()       # one recording at a time: the model is the bottleneck anyway


def worker_command():
    if os.environ.get("SMARTWARD_STT_WORKER_CMD"): return os.environ["SMARTWARD_STT_WORKER_CMD"].split()
    return [str(DIR / ".venv/bin/python"), str(DIR / "worker.py"), str(DIR / "models" / model_name())]


def _worker():
    p = _w["proc"]
    if p is not None and p.poll() is None: return p
    p = subprocess.Popen(worker_command(), cwd=str(DIR), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    first = json.loads(p.stdout.readline() or "{}")
    if not first.get("ready"):
        p.kill(); raise RuntimeError(first.get("error") or "The speech model didn't start.")
    _w["proc"] = p
    threading.Thread(target=_worker_idle, args=(p,), daemon=True).start()
    return p


def _worker_idle(p):
    while p.poll() is None:
        time.sleep(5)
        if time.time() - _w["used"] > WORKER_IDLE_S: stop_worker(p); return


def stop_worker(p=None):
    with _wlock if p is None else threading.Lock():
        p = p or _w["proc"]
        if p is None: return
        try: p.stdin.close()
        except Exception: pass
        try: p.wait(timeout=3)
        except subprocess.TimeoutExpired: p.kill()
        if _w["proc"] is p: _w["proc"] = None


def transcribe(path, timeout=180):
    """The text in an audio file (wav, webm, mp4, ogg...). Raises RuntimeError when speech input isn't available."""
    if not installed(): raise RuntimeError("Speech input isn't installed on the laptop. Run stt/setup.sh.")
    with _wlock:
        p = _worker(); _w["used"] = time.time(); _w["id"] += 1; rid = _w["id"]
        p.stdin.write(json.dumps({"id": rid, "path": str(path)}) + "\n"); p.stdin.flush()
        box = []
        t = threading.Thread(target=lambda: box.append(p.stdout.readline()), daemon=True); t.start(); t.join(timeout)
        if not box or not box[0]:
            try: p.kill()
            except Exception: pass
            _w["proc"] = None; raise RuntimeError("The speech model took too long. Try again.")
        res = json.loads(box[0]); _w["used"] = time.time()
        if res.get("error"): raise RuntimeError(res["error"])
        return res.get("text", "")
