"""What Tailscale says about this laptop, so Settings can show the private https address and whether it is published."""
import json, os, shutil, subprocess


def _run(args, timeout=6):
    exe = os.environ.get("SMARTWARD_TAILSCALE_CMD") or shutil.which("tailscale")
    if not exe: return None
    try: return subprocess.run([*exe.split(), *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired): return None


def info():
    r = _run(["status", "--json"])
    if r is None: return {"installed": False}
    try: d = json.loads(r.stdout or "{}")
    except ValueError: d = {}
    me = d.get("Self") or {}; users = d.get("User") or {}
    dns = (me.get("DNSName") or "").rstrip(".")
    login = (users.get(str(me.get("UserID"))) or {}).get("LoginName", "")
    state = d.get("BackendState") or ("Stopped" if r.returncode else "Unknown")
    serve = _run(["serve", "status"]); text = (serve.stdout if serve and serve.returncode == 0 else "") or ""
    return {"installed": True, "state": state, "dns_name": dns, "login": login, "https_url": f"https://{dns}" if dns else "",
            "published": bool(dns) and dns in text and "8000" in text, "serve_command": "tailscale serve --bg 127.0.0.1:8000"}
