"""Phone notifications through the phone's own push service (Web Push), so they arrive while SmartWard is closed on the phone.

The text is always generic ("SmartWard: 2 watch matches"): the push service carries it (encrypted), and the details are only shown once you open
SmartWard. Subscriptions can only point at the browser vendors' push services, so a phone session can't make the laptop send requests anywhere
else. The signing key stays on the laptop: it is never returned by the settings API and never goes into a backup. A daily cap stops a busy feed
from buzzing your phone all day."""
import base64, json, time
from urllib.parse import urlparse
from . import db

PUSH_HOSTS = ("fcm.googleapis.com", "android.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com", "web.push.apple.com")
PUSH_SUFFIXES = (".push.apple.com", ".notify.windows.com", ".push.services.mozilla.com")
CONTACT = "https://github.com/AnubisRooster/smartward-laptop"      # the "who sent this" a push service asks for; no personal address
MAX_SUBS = 10


def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def keys():
    """(private PEM, public key for the browser), made once."""
    priv, pub = db.get_setting("push_vapid_private"), db.get_setting("push_vapid_public")
    if priv and pub: return priv, pub
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
    v = Vapid(); v.generate_keys()
    priv = v.private_pem().decode(); pub = _b64(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    db.set_setting("push_vapid_private", priv); db.set_setting("push_vapid_public", pub)
    return priv, pub


def allowed_endpoint(url):
    u = urlparse(url or "")
    host = (u.hostname or "").lower()
    return u.scheme == "https" and not u.username and not u.password and (u.port in (None, 443)) and (host in PUSH_HOSTS or host.endswith(PUSH_SUFFIXES))


def subscribe(sub, label=""):
    if not isinstance(sub, dict): raise ValueError("Not a push subscription.")
    ep = sub.get("endpoint"); k = sub.get("keys") or {}
    if not allowed_endpoint(ep): raise ValueError("That isn't a known push service.")
    if not (isinstance(k, dict) and isinstance(k.get("p256dh"), str) and isinstance(k.get("auth"), str) and len(k["p256dh"]) < 200 and len(k["auth"]) < 100): raise ValueError("The subscription has no keys.")
    if not db.q("SELECT 1 FROM push_subs WHERE endpoint=?", (ep,), one=True) and db.q("SELECT COUNT(*) n FROM push_subs", one=True)["n"] >= MAX_SUBS:
        raise ValueError(f"At most {MAX_SUBS} devices can get notifications. Turn one off first.")
    db.x("INSERT INTO push_subs(endpoint,keys,label,created,fails) VALUES(?,?,?,?,0) ON CONFLICT(endpoint) DO UPDATE SET keys=excluded.keys, label=excluded.label, fails=0",
         (ep, json.dumps({"p256dh": k["p256dh"], "auth": k["auth"]}), str(label or "")[:60], db.now()))
    return {"ok": True}


def unsubscribe(endpoint): db.x("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))


def devices(): return db.q("SELECT id,label,created,last_ok,fails FROM push_subs ORDER BY created")


def _send_one(sub, payload):
    from pywebpush import webpush, WebPushException
    from py_vapid import Vapid
    priv, _ = keys()
    try:
        webpush({"endpoint": sub["endpoint"], "keys": json.loads(sub["keys"])}, json.dumps(payload), vapid_private_key=Vapid.from_pem(priv.encode()),
                vapid_claims={"sub": CONTACT}, ttl=12 * 3600, timeout=15)
        db.x("UPDATE push_subs SET last_ok=?, fails=0 WHERE id=?", (db.now(), sub["id"])); return True
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        if code in (404, 410): unsubscribe(sub["endpoint"])                    # the phone dropped it (app removed, permission revoked)
        else: db.x("UPDATE push_subs SET fails=fails+1 WHERE id=?", (sub["id"],))
    except Exception: db.x("UPDATE push_subs SET fails=fails+1 WHERE id=?", (sub["id"],))
    return False


def _under_cap():
    today = time.strftime("%Y-%m-%d"); sent = db.get_setting("push_sent") or {}
    n = sent.get("n", 0) if sent.get("day") == today else 0
    if n >= int(db.get_setting("push_daily_cap") or 6): return False
    db.set_setting("push_sent", {"day": today, "n": n + 1}); return True


def send(title, body="Open SmartWard to see details.", url="/#/radar", tag="smartward", endpoint=None, capped=True):
    """Send to every subscribed device (or one). Returns how many got it. Text must be generic: it is shown on a lock screen."""
    subs = db.q("SELECT * FROM push_subs" + (" WHERE endpoint=?" if endpoint else ""), (endpoint,) if endpoint else ())
    if not subs or (capped and not _under_cap()): return 0
    payload = {"title": title[:80], "body": body[:120], "url": url if url.startswith("/") else "/", "tag": tag}
    return sum(_send_one(s, payload) for s in subs)


def announce(hits, watches_hit, memo_week=None):
    """The generic notifications for what's new. Nothing about titles or sources goes to the push service."""
    sent = 0
    if hits: sent += send(f"SmartWard: {hits} watch match{'es' if hits != 1 else ''}", "Open SmartWard to see them.", "/#/radar", "watches")
    if memo_week: sent += send("SmartWard: this week’s memo is ready", "Open SmartWard to read it.", "/#/radar", "memo")
    return sent
