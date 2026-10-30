import unittest
from sw import db, remote
from tests import helpers as h

c = h.client
HOST = "laptop.tail1234.ts.net"
VIA = {"Host": HOST, "X-Forwarded-For": "100.64.0.9", "X-Forwarded-Proto": "https", "Tailscale-User-Login": "me@example.com"}


def turn_on(login="me@example.com", passphrase="correct horse battery"):
    r = c.put("/api/remote/config", json={"login": login, "passphrase": passphrase, "enabled": True}); assert r.status_code == 200, r.text


def sign_in(passphrase="correct horse battery", headers=None):
    """The test client talks http, so it would not send a Secure cookie back; carry the cookie by hand like a browser on https."""
    r = c.post("/api/remote/login", json={"passphrase": passphrase}, headers=headers or VIA)
    if r.status_code == 200 and headers is None: VIA["Cookie"] = "sw_remote=" + r.headers["set-cookie"].split("sw_remote=")[1].split(";")[0]
    return r


class LocalUseIsUnchanged(unittest.TestCase):
    def setUp(self): h.reset(); remote.clear_failures(); VIA.pop("Cookie", None)

    def test_the_local_window_needs_no_sign_in_even_with_remote_on(self):
        turn_on(); self.assertEqual(c.get("/api/status").status_code, 200); self.assertEqual(c.get("/api/settings").status_code, 200)
        self.assertEqual(c.get("/api/status", headers={"Host": "127.0.0.1:8000"}).status_code, 200)
        self.assertEqual(c.get("/api/status", headers={"Host": "localhost:8000"}).status_code, 200)
        self.assertEqual(c.get("/api/status", headers={"Host": "[::1]:8000"}).status_code, 200)

    def test_a_web_page_cannot_reach_the_api_by_rebinding_its_own_name(self):
        r = c.get("/api/settings", headers={"Host": "evil.example.com:8000"}); self.assertEqual(r.status_code, 400)

    def test_remote_settings_never_come_back_or_get_written_through_settings(self):
        turn_on(); s = c.get("/api/settings").json()
        self.assertTrue(s["remote_hash"] is True); self.assertNotIn("remote_sessions", s); self.assertNotIn("remote_log", s)
        c.put("/api/settings", json={"values": {"remote_enabled": False, "remote_hash": "x", "remote_login": "evil@example.com"}})
        self.assertTrue(remote.enabled()); self.assertEqual(db.get_setting("remote_login"), "me@example.com")


class TheFrontDoor(unittest.TestCase):
    def setUp(self): h.reset(); remote.clear_failures(); VIA.pop("Cookie", None)

    def test_off_by_default_even_if_the_proxy_is_running(self):
        r = c.get("/api/status", headers=VIA); self.assertEqual(r.status_code, 403); self.assertIn("turned off", r.json()["detail"])

    def test_cannot_be_turned_on_without_a_passphrase_and_login(self):
        self.assertEqual(c.put("/api/remote/config", json={"enabled": True}).status_code, 400)
        self.assertEqual(c.put("/api/remote/config", json={"passphrase": "short"}).status_code, 400)

    def test_the_app_shell_loads_without_a_session_but_the_api_does_not(self):
        turn_on(); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)
        self.assertTrue(c.get("/api/status", headers=VIA).json()["remote_auth"])
        self.assertNotEqual(c.get("/", headers=VIA).status_code, 401)           # the page itself, so it can show the sign-in

    def test_wrong_passphrase_is_refused_then_the_right_one_signs_in(self):
        turn_on(); self.assertEqual(sign_in("nope nope nope").status_code, 403)
        r = sign_in(); self.assertEqual(r.status_code, 200)
        cookie = r.headers["set-cookie"].lower()
        for flag in ("httponly", "secure", "samesite=strict"): self.assertIn(flag, cookie)
        self.assertEqual(c.get("/api/status", headers=VIA).status_code, 200)       # the client keeps the cookie
        self.assertTrue(c.get("/api/remote/session", headers=VIA).json()["signed_in"])

    def test_five_wrong_tries_lock_sign_in_for_a_while(self):
        turn_on()
        for _ in range(5): sign_in("wrong wrong wrong")
        self.assertEqual(sign_in().status_code, 429)                                # even the right one, until the lock ends
        remote.clear_failures(); self.assertEqual(sign_in().status_code, 200)

    def test_a_signed_in_phone_can_read_and_chat_but_not_change_settings_or_leave_with_the_library(self):
        turn_on(); sign_in()
        for path in ("/api/status", "/api/articles", "/api/digest", "/api/conversations", "/api/projects", "/api/search?q=x"):
            self.assertEqual(c.get(path, headers=VIA).status_code, 200, path)
        for method, path in (("post", "/api/backup"), ("post", "/api/restore"), ("get", "/api/export/json"), ("get", "/api/export/markdown"),
                             ("post", "/api/danger/erase"), ("post", "/api/lock/set"), ("get", "/api/dev/info"), ("post", "/api/voice/start"), ("get", "/api/voice/poll"),
                             ("post", "/api/sources"), ("delete", "/api/sources/1"), ("put", "/api/remote/config"), ("get", "/api/remote/status"), ("post", "/api/remote/revoke"),
                             ("post", "/api/events/poll")):
            r = getattr(c, method)(path, headers=VIA, **({"json": {}} if method in ("put", "post") else {})); self.assertEqual(r.status_code, 403, f"{method} {path}")

    def test_only_the_allowed_tailscale_account_gets_in(self):
        turn_on(); other = {**VIA, "Tailscale-User-Login": "someone@else.com"}
        self.assertEqual(sign_in(headers=other).status_code, 403); self.assertEqual(c.get("/api/status", headers=other).status_code, 403)

    def test_only_the_tailscale_host_name_is_accepted(self):
        turn_on(); self.assertEqual(c.get("/api/status", headers={**VIA, "Host": "evil.example.com"}).status_code, 403)
        c.put("/api/remote/config", json={"host": HOST}); self.assertEqual(c.get("/api/status", headers={**VIA, "Host": "other.ts.net"}).status_code, 403)

    def test_cross_site_writes_are_refused_even_with_a_session(self):
        turn_on(); sign_in()
        r = c.post("/api/articles/mark-read", json={"ids": []}, headers={**VIA, "Origin": "https://evil.example.com"}); self.assertEqual(r.status_code, 403)
        r = c.post("/api/articles/mark-read", json={"ids": []}, headers={**VIA, "Origin": f"https://{HOST}"}); self.assertEqual(r.status_code, 200)

    def test_sign_out_and_revoke_end_the_session(self):
        turn_on(); sign_in(); self.assertEqual(c.post("/api/remote/logout", headers=VIA).status_code, 200)
        self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)             # the old cookie no longer works
        VIA.pop("Cookie"); sign_in(); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 200)
        sid = remote.list_sessions()[0]["id"]; c.post("/api/remote/revoke", json={"id": sid})
        self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)

    def test_the_passphrase_is_stored_hashed_and_sessions_by_digest(self):
        turn_on(); sign_in()
        self.assertNotIn("correct horse", str(db.get_setting("remote_hash")))
        token = VIA["Cookie"].split("=")[1]; self.assertNotIn(token, str(db.get_setting("remote_sessions")))

    def test_an_old_session_expires(self):
        turn_on(); sign_in(); s = db.get_setting("remote_sessions")
        for v in s.values(): v["last"] -= remote.SESSION_SECONDS + 5
        db.set_setting("remote_sessions", s); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)

    def test_api_answers_to_a_phone_are_not_cached(self):
        turn_on(); sign_in(); self.assertEqual(c.get("/api/status", headers=VIA).headers["cache-control"], "no-store")


class Pieces(unittest.TestCase):
    def test_host_names(self):
        self.assertEqual(remote.host_of({"host": "Laptop.ts.net:443"}), "laptop.ts.net"); self.assertEqual(remote.host_of({"host": "[::1]:8000"}), "::1")
        self.assertEqual(remote.host_of({}), "")

    def test_passphrase_hash_round_trip(self):
        x = remote.hash_pass("a long passphrase"); self.assertTrue(remote.check_pass("a long passphrase", x)); self.assertFalse(remote.check_pass("another one", x))
        self.assertFalse(remote.check_pass("x", "garbage"))


if __name__ == "__main__":
    unittest.main()


class PhoneSettings(unittest.TestCase):
    def setUp(self): h.reset(); remote.clear_failures(); VIA.pop("Cookie", None); turn_on(); sign_in()

    def put(self, values): return c.put("/api/settings", json={"values": values}, headers=VIA)

    def test_a_phone_can_change_the_model_the_budget_and_the_voice(self):
        r = self.put({"model": "openrouter/poolside/laguna-s-2.1:free", "daily_budget": 2.5, "cloud_scope": "chat", "voice_rate": 1.1, "tts_engine": "browser"}); self.assertEqual(r.status_code, 200, r.text)
        s = c.get("/api/settings").json(); self.assertEqual((s["model"], s["daily_budget"], s["cloud_scope"]), ("openrouter/poolside/laguna-s-2.1:free", 2.5, "chat"))
        for path in ("/api/usage", "/api/models"): self.assertEqual(c.get(path, headers=VIA).status_code, 200, path)

    def test_keys_addresses_and_the_lock_stay_laptop_only(self):
        for values in ({"api_key": "sk-evil"}, {"ollama_base": "http://evil.example.com"}, {"tts_url": "http://evil.example.com"}, {"github_token": "x"}, {"lock_after": 0},
                       {"interests": "x"}, {"model": "openrouter/x", "api_key": "sk-evil"}, {"remote_login": "evil@example.com"}):
            r = self.put(values); self.assertEqual(r.status_code, 403, values); self.assertIn("laptop", r.json()["detail"])
        self.assertNotEqual(h.db.get_setting("api_key"), "sk-evil"); self.assertNotEqual(h.db.get_setting("ollama_base"), "http://evil.example.com")

    def test_a_phone_can_only_pick_local_or_openrouter_models(self):
        for bad in ("hosted_vllm/http://evil", "openai/gpt-4o", 123):
            self.assertEqual(self.put({"model": bad}).status_code, 403, bad)
        self.assertEqual(self.put({"model": "ollama_chat/llama3.2:3b"}).status_code, 200)

    def test_the_laptop_itself_is_not_limited(self):
        self.assertEqual(c.put("/api/settings", json={"values": {"interests": "kv cache"}}).status_code, 200)
