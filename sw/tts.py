"""Natural read-aloud voice: a thin proxy to a text-to-speech server on this machine.

The server speaks the OpenAI /v1/audio/speech API (Kokoro: tts/server.py, or Kokoro-FastAPI).
Only loopback addresses are allowed, so article text never leaves this computer.
"""
import re
from urllib.parse import urlparse
import httpx
from . import db

DEFAULT_URL = "http://127.0.0.1:8880"
VOICE_RE = re.compile(r"^[a-z]{2}_[a-z0-9_]{1,36}$")
SPEED = (0.5, 2.0)
MAX_TEXT = 3000
MAX_PROFILES = 24

def is_loopback(url: str) -> bool:
    try: host = (urlparse(url).hostname or "").lower()
    except Exception: return False
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")

def base() -> str:
    url = (db.get_setting("tts_url") or DEFAULT_URL).rstrip("/")
    if not is_loopback(url): raise ValueError("The speech server must be on this computer (127.0.0.1 or localhost).")
    return url

def voices() -> list:
    for path in ("/v1/voices", "/v1/audio/voices"):
        try:
            r = httpx.get(base() + path, timeout=3)
            if r.status_code == 200: return sorted(r.json().get("voices", []))
        except Exception: pass
    return []

def status() -> dict:
    try: url = base()
    except ValueError as e: return {"up": False, "voices": [], "url": db.get_setting("tts_url"), "error": str(e)}
    try:
        up = httpx.get(url + "/health", timeout=2).status_code == 200
    except Exception:
        up = False
    return {"up": up, "voices": voices() if up else [], "url": url}

def synth(text: str, voice: str, speed: float) -> bytes:
    text = (text or "").strip()
    if not text: raise ValueError("Nothing to read.")
    if len(text) > MAX_TEXT: raise ValueError(f"Text is too long ({len(text)} characters; the limit is {MAX_TEXT}).")
    if not VOICE_RE.match(voice or ""): raise ValueError("That isn't a voice name like af_heart.")
    if not (SPEED[0] <= speed <= SPEED[1]): raise ValueError("Speed must be between 0.5 and 2.")
    r = httpx.post(base() + "/v1/audio/speech", json={"model": "kokoro", "input": text, "voice": voice, "speed": speed, "response_format": "wav"}, timeout=180)
    if r.status_code != 200: raise RuntimeError(f"The speech server answered {r.status_code}: {r.text[:200]}")
    return r.content

def validate_setting(key: str, value, incoming: dict | None = None):
    """Raises ValueError for a speech setting that shouldn't be saved."""
    if key == "tts_url":
        if not isinstance(value, str) or not is_loopback(value): raise ValueError("The speech server must be on this computer (127.0.0.1 or localhost).")
    elif key == "tts_engine":
        if value not in ("auto", "kokoro", "browser"): raise ValueError("Engine must be auto, kokoro or browser.")
    elif key == "tts_voice":
        if not isinstance(value, str) or not VOICE_RE.match(value): raise ValueError("That isn't a voice name like af_heart.")
    elif key == "voice_rate":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not (SPEED[0] <= value <= SPEED[1]): raise ValueError("Speed must be between 0.5 and 2.")
    elif key == "tts_profiles":
        if not isinstance(value, dict) or len(value) > MAX_PROFILES: raise ValueError(f"At most {MAX_PROFILES} profiles.")
        for name, p in value.items():
            if not isinstance(name, str) or not (1 <= len(name.strip()) <= 40): raise ValueError("Profile names are 1–40 characters.")
            if not isinstance(p, dict) or not VOICE_RE.match(str(p.get("voice", ""))): raise ValueError(f"Profile “{name}” needs a voice like af_heart.")
            rate = p.get("rate")
            if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not (SPEED[0] <= rate <= SPEED[1]): raise ValueError(f"Profile “{name}” needs a speed between 0.5 and 2.")
    elif key == "tts_profile":
        profiles = (incoming or {}).get("tts_profiles", db.get_setting("tts_profiles")) or {}
        if value and value not in profiles: raise ValueError(f"There's no profile called “{value}”.")
