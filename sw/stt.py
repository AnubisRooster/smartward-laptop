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
    stop()
    with _lock: _events.clear(); _seq = 0; _state.update(ready=False, state="off", error="")
