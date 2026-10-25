"""While remote access is on, ask the system not to sleep (so a phone can still reach the laptop). Uses systemd-inhibit and holds
the lock only while SmartWard runs. Closing the lid still suspends the laptop: that is a system setting SmartWard does not change."""
import os, shutil, subprocess, threading
from . import db

_lock = threading.Lock()
_proc = None


def command():
    if os.environ.get("SMARTWARD_INHIBIT_CMD"): return os.environ["SMARTWARD_INHIBIT_CMD"].split()
    exe = shutil.which("systemd-inhibit")
    return [exe, "--what=sleep:idle", "--who=SmartWard", "--why=Remote access is on", "--mode=block", "sleep", "infinity"] if exe else None


def running():
    return _proc is not None and _proc.poll() is None


def hold():
    global _proc
    with _lock:
        if running(): return True
        cmd = command()
        if not cmd: return False
        try: _proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: return False
        return True


def release():
    global _proc
    with _lock:
        p, _proc = _proc, None
    if p is not None and p.poll() is None:
        p.terminate()
        try: p.wait(timeout=3)
        except subprocess.TimeoutExpired: p.kill()


def sync():
    """Hold the lock exactly when remote access is on and the keep-awake setting is on."""
    want = bool(db.get_setting("remote_enabled")) and db.get_setting("remote_keep_awake") is not False
    if want: hold()
    else: release()
    return running()
