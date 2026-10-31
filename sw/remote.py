"""The front door for reaching SmartWard from a phone (through Tailscale Serve).

The API itself still listens on 127.0.0.1 only. A request that came through the proxy carries forwarded headers; it is
"remote" and must pass every check below. A request without them is the local window and keeps working as it always did
(its Host must still be a loopback name, which stops a web page from reaching the API by rebinding its own DNS name).
All state lives in settings, so there is no schema change. Everything here is pure or reads settings: easy to test."""
import hashlib, hmac, json, re, secrets, threading, time
from urllib.parse import urlparse
from . import db

COOKIE = "sw_remote"
SESSION_SECONDS = 30 * 86400
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
FORWARDED = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "tailscale-user-login")
SAFE = ("GET", "HEAD", "OPTIONS")

# What a signed-in phone may do. Everything else is refused: settings and keys, backups and exports, erasing, the app lock,
# changing sources, and the laptop's own microphone.
_R = lambda m, p: (m, re.compile("^" + p + "$"))
ALLOW = [
    _R("GET", r"/api/(status|settings|sources|digest|graph|themes|projects|domains|signals|developments|developments/status|memos|memo/status|implications/status|chat/modes|conversations|approvals|search|tts/status|articles|help)"),
    _R("GET", r"/api/(articles|themes|projects|conversations|memos)/\d+"), _R("GET", r"/api/export/share/(memo|project)/\d+"),
    _R("POST", r"/api/articles/mark-read"), _R("POST", r"/api/articles/\d+/(summary|full|discuss)"), _R("PATCH", r"/api/articles/\d+"),
    _R("POST", r"/api/share"), _R("POST", r"/api/tts"), _R("POST", r"/api/voice/transcribe"),
    _R("POST", r"/api/conversations"), _R("POST", r"/api/conversations/\d+/(send|cancel)"), _R("DELETE", r"/api/conversations/\d+"),
    _R("POST", r"/api/approvals/[0-9a-f]+"), _R("POST", r"/api/projects/\d+/items"), _R("GET", r"/api/projects/\d+/implications"), _R("POST", r"/api/implications/\d+/(accept|dismiss)"), _R("PATCH", r"/api/items/\d+"),
    _R("POST", r"/api/remote/logout"),
    _R("GET", r"/api/(watches|push/key)"), _R("POST", r"/api/watches"), _R("PUT", r"/api/watches/\d+"), _R("DELETE", r"/api/watches/\d+"),
    _R("POST", r"/api/push/(subscribe|unsubscribe|test)"),
    _R("GET", r"/api/projects/\d+/map"),
    _R("GET", r"/api/(usage|models|openrouter/models)"), _R("POST", r"/api/models/test"), _R("PUT", r"/api/settings"),     # the phone's Settings: only the keys below
]

# What a phone may change in Settings: the model, the budget and the voice. Never keys, addresses, the lock, sources or remote access itself:
# a phone session that could change the API key or a server address could redirect your data elsewhere.
PHONE_SETTINGS = {"model", "cloud_scope", "analysis_model", "daily_budget", "tts_engine", "tts_voice", "tts_profile", "tts_profiles", "voice_rate", "voice_name"}
PHONE_MODEL_PREFIXES = ("ollama_chat/", "openrouter/")


def phone_settings_refusal(values):
    """None when a phone may save these settings, else a plain reason."""
    other = sorted(k for k in values if k not in PHONE_SETTINGS)
    if other: return "These can only be changed on the laptop: " + ", ".join(other) + "."
    for k in ("model", "analysis_model"):
        v = values.get(k)
        if v not in (None, "") and not (isinstance(v, str) and v.startswith(PHONE_MODEL_PREFIXES)): return "From a phone, pick a local (Ollama) or OpenRouter model."
    return None
PUBLIC = [_R("POST", r"/api/remote/login"), _R("GET", r"/api/remote/session")]

_lock = threading.Lock()
_fails = []          # times of recent wrong passphrases
_locked_until = [0.0]


def host_of(headers):
    """The Host header without its port: `laptop.ts.net:443` -> `laptop.ts.net`, `[::1]:8000` -> `::1`."""
    h = (headers.get("host") or "").strip().lower()
    if h.startswith("[") and "]" in h: return h[1:h.index("]")]
    return h.split(":")[0] if h.count(":") == 1 else h


def is_remote(headers):
    return any(k in headers for k in FORWARDED)


def enabled(): return bool(db.get_setting("remote_enabled"))


def _matches(rules, method, path): return any(m == method and r.match(path) for m, r in rules)


def host_ok(host):
    want = (db.get_setting("remote_host") or "").strip().lower()
    return host == want if want else host.endswith(".ts.net")


# ---- passphrase and sessions ----
def hash_pass(p):
    salt = secrets.token_bytes(16)
    return salt.hex() + ":" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt, 200_000).hex()


def check_pass(p, stored):
    try:
        salt, h = stored.split(":")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000).hex(), h)
    except Exception:
        return False


def _digest(token): return hashlib.sha256(token.encode()).hexdigest()


def _sessions(): return db.get_setting("remote_sessions") or {}


def new_session(user_agent=""):
    token = secrets.token_urlsafe(32)
    with _lock:
        s = _sessions(); now = time.time()
        s = {k: v for k, v in s.items() if now - v["last"] < SESSION_SECONDS}
        s[_digest(token)] = {"created": now, "last": now, "agent": (user_agent or "")[:120]}
        db.set_setting("remote_sessions", s)
    return token


def valid_session(token):
    """The session's id when the cookie is good (and slides its expiry), else None."""
    if not token: return None
    d = _digest(token)
    with _lock:
        s = _sessions(); v = s.get(d); now = time.time()
        if not v or now - v["last"] > SESSION_SECONDS: return None
        if now - v["last"] > 600: v["last"] = now; db.set_setting("remote_sessions", s)
    return d[:8]


def list_sessions():
    return [{"id": k[:8], "created": v["created"], "last": v["last"], "agent": v.get("agent", "")} for k, v in sorted(_sessions().items(), key=lambda kv: -kv[1]["last"])]


def revoke(which):
    with _lock:
        s = _sessions()
        s = {} if which == "all" else {k: v for k, v in s.items() if k[:8] != which}
        db.set_setting("remote_sessions", s)


def log(event, detail=""):
    with _lock:
        entries = (db.get_setting("remote_log") or [])[-49:] + [{"ts": time.time(), "event": event, "detail": detail[:160]}]
        db.set_setting("remote_log", entries)


# ---- throttle ----
def locked_for():
    return max(0.0, _locked_until[0] - time.time())


def record_failure():
    now = time.time()
    with _lock:
        _fails[:] = [t for t in _fails if now - t < 900] + [now]
        if len(_fails) >= 5: _locked_until[0] = now + 300; _fails.clear()


def clear_failures():
    with _lock: _fails.clear(); _locked_until[0] = 0.0


# ---- the decision ----
def decide(method, path, headers, cookie=None):
    """None to let the request through, or (status, message) to refuse it."""
    host = host_of(headers)
    if not is_remote(headers):
        return None if host in LOCAL_HOSTS else (400, "Unexpected host name.")
    if not enabled(): return (403, "Remote access is turned off on this computer.")
    if not host_ok(host): return (403, "Unexpected host name.")
    want = (db.get_setting("remote_login") or "").strip().lower()
    if want and (headers.get("tailscale-user-login") or "").strip().lower() != want: return (403, "This Tailscale account isn't allowed.")
    origin = headers.get("origin")
    if origin and method not in SAFE and (urlparse(origin).hostname or "").lower() != host: return (403, "Cross-site request refused.")
    if not path.startswith("/api/"): return None                      # the app itself (page, scripts, icons), so it can show the sign-in
    if _matches(PUBLIC, method, path): return None
    if not valid_session(cookie): return (401, "Sign in required.")
    if not _matches(ALLOW, method, path): return (403, "That isn't available from a phone.")
    return None
