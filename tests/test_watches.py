import json, time, unittest
from types import SimpleNamespace as NS
from unittest import mock
from sw import db, events, push, watches
from tests import helpers as h
from tests.test_implications import dev

c = h.client
NOW = time.time()
SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc123", "keys": {"p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM", "auth": "tBHItJI5svbpez7KI4CCXg"}}


class Setup(unittest.TestCase):
    def setUp(self):
        h.reset(); events.reset()
        self.src = h.add_source("Release notes"); self.other = h.add_source("Someone's blog")

    def art(self, title, text="", src=None, ago=1, **kw):
        a = h.add_article(src or self.src, title, text or ("x " * 300), **kw); db.x("UPDATE articles SET created=? WHERE id=?", (NOW - ago * 3600, a)); return a

    def dev_for(self, a, claim, evidence="measured", domains=("Speculative decoding",), ago=1):
        d = dev(a, claim=claim, evidence=evidence, domains=domains); db.x("UPDATE developments SET created=? WHERE id=?", (NOW - ago * 3600, d)); return d


class Matching(Setup):
    def test_a_new_watch_looks_back_two_weeks_without_announcing(self):
        self.art("SGLang adds speculative decoding", ago=24 * 3); self.art("Old news about SGLang", ago=24 * 30)
        w = watches.create({"terms": ["sglang", "vllm"]}, NOW)
        self.assertEqual(w["name"], "sglang, vllm"); self.assertEqual(len(watches.listing()[0]["hits"]), 1)
        self.assertEqual(watches.unannounced(), (0, 0))

    def test_new_articles_match_by_whole_word_and_are_announced_once(self):
        w = watches.create({"name": "Serving engines", "terms": ["vllm"]}, NOW - 3600 * 5)
        self.art("vLLM 0.12 released", ago=1); self.art("vllmish nonsense", ago=1); self.art("Unrelated", ago=1)
        self.assertEqual(watches.scan(NOW), 1); self.assertEqual(watches.scan(NOW), 0)
        self.assertEqual(watches.unannounced(), (1, 1)); self.assertEqual(watches.unannounced(), (0, 0))

    def test_measured_only_watches_need_a_measured_development_and_the_hit_carries_it(self):
        watches.create({"terms": ["speculative decoding"], "min_evidence": "measured"}, NOW - 3600 * 5)
        a = self.art("Speculative decoding on CPUs", ago=1); b = self.art("Speculative decoding hype", ago=1)
        d = self.dev_for(a, "Speculative decoding gives 1.8x on CPU."); self.dev_for(b, "Speculative decoding is the future.", evidence="claimed")
        watches.scan(NOW); hits = watches.listing()[0]["hits"]
        self.assertEqual([x["article_id"] for x in hits], [a]); self.assertEqual(hits[0]["dev_id"], d)

    def test_domain_and_source_limits_and_private_articles_never_match(self):
        watches.create({"domains": ["Speculative decoding"], "sources": [self.src]}, NOW - 3600 * 5)
        a = self.art("EAGLE-3 draft models", ago=1); self.art("EAGLE-3 draft models again", src=self.other, ago=1)
        self.art("Medusa heads in my private notes", ago=1, private=1); self.art("A recipe for soup", ago=1)
        watches.scan(NOW); self.assertEqual([x["article_id"] for x in watches.listing()[0]["hits"]], [a])

    def test_disabled_watches_are_skipped_and_bad_input_is_refused(self):
        w = watches.create({"terms": ["vllm"]}, NOW - 3600 * 5); watches.update(w["id"], {"enabled": False})
        self.art("vLLM news", ago=1); self.assertEqual(watches.scan(NOW), 0)
        with self.assertRaises(ValueError): watches.create({"name": "nothing"})
        with self.assertRaises(ValueError): watches.create({"terms": ["x"], "min_evidence": "rumour"})
        with self.assertRaises(ValueError): watches.update(w["id"], {"name": ""})

    def test_a_desktop_notification_for_new_matches_but_not_for_look_back_ones(self):
        db.set_setting("notify_articles", False); events.poll()
        self.art("SGLang adds speculative decoding", ago=24 * 3); watches.create({"terms": ["sglang"]}, NOW - 600)
        self.assertEqual(events.poll(), [])
        self.art("SGLang again", ago=0); watches.scan(NOW + 1)
        self.assertEqual([e["kind"] for e in events.poll()], ["watch"])


class Push(Setup):
    def test_the_signing_key_is_made_once_and_never_shown_or_backed_up(self):
        priv, pub = push.keys(); self.assertEqual(push.keys(), (priv, pub)); self.assertEqual(len(pub), 87)
        s = c.get("/api/settings").json(); self.assertIs(s["push_vapid_private"], True); self.assertNotIn(priv, json.dumps(s))
        c.put("/api/settings", json={"values": {"push_vapid_private": "evil", "push_daily_cap": 3}})
        self.assertEqual(db.get_setting("push_vapid_private"), priv); self.assertEqual(db.get_setting("push_daily_cap"), 3)
        self.assertNotIn("push_vapid_private", json.dumps(h.api._dump()))
        self.assertNotIn("push_subs", h.api.TABLES)

    def test_only_real_push_services_can_be_subscribed(self):
        self.assertTrue(push.allowed_endpoint("https://web.push.apple.com/QGuQ"))
        self.assertTrue(push.allowed_endpoint("https://updates.push.services.mozilla.com/wpush/v2/x"))
        for bad in ("http://fcm.googleapis.com/x", "https://evil.example.com/x", "https://fcm.googleapis.com.evil.com/x", "https://user@fcm.googleapis.com/x",
                    "https://127.0.0.1/x", "https://fcm.googleapis.com:8443/x", "javascript:alert(1)", ""):
            self.assertFalse(push.allowed_endpoint(bad), bad)
        with self.assertRaises(ValueError): push.subscribe({"endpoint": "https://evil.example.com/x", "keys": SUB["keys"]})
        with self.assertRaises(ValueError): push.subscribe({"endpoint": SUB["endpoint"]})
        push.subscribe(SUB, "Pixel"); push.subscribe(SUB, "Pixel again"); self.assertEqual([d["label"] for d in push.devices()], ["Pixel again"])

    def test_sending_is_generic_capped_and_drops_gone_devices(self):
        push.subscribe(SUB); db.set_setting("push_daily_cap", 2); sent = []
        with mock.patch("pywebpush.webpush", side_effect=lambda info, data, **kw: sent.append(json.loads(data))):
            self.assertEqual(push.announce(3, 1), 1); self.assertEqual(push.announce(1, 1, "2026-W44"), 1)       # second call: watches sent, memo over the cap
            self.assertEqual(push.announce(1, 1), 0)
        self.assertEqual(sent[0]["title"], "SmartWard: 3 watch matches"); self.assertEqual(len(sent), 2)
        from pywebpush import WebPushException
        gone = WebPushException("gone", response=NS(status_code=410, text=""))
        with mock.patch("pywebpush.webpush", side_effect=gone): push.send("t", capped=False)
        self.assertEqual(push.devices(), [])

    def test_the_phone_can_subscribe_test_and_manage_watches_but_not_change_push_settings(self):
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(len(c.get("/api/push/key", headers=VIA).json()["public_key"]), 87)
        self.assertEqual(c.post("/api/push/subscribe", json={"subscription": SUB, "label": "Moto"}, headers=VIA).status_code, 200)
        with mock.patch("pywebpush.webpush") as wp:
            self.assertEqual(c.post("/api/push/test", json={"endpoint": SUB["endpoint"]}, headers=VIA).status_code, 200); wp.assert_called_once()
        self.assertEqual(c.post("/api/push/test", json={"endpoint": "https://fcm.googleapis.com/other"}, headers=VIA).status_code, 404)
        r = c.post("/api/watches", json={"terms": ["vllm"]}, headers=VIA); self.assertEqual(r.status_code, 200)
        self.assertEqual(c.put(f"/api/watches/{r.json()['id']}", json={"enabled": False}, headers=VIA).status_code, 200)
        self.assertEqual(c.delete(f"/api/watches/{r.json()['id']}", headers=VIA).status_code, 200)
        self.assertEqual(c.put("/api/settings", json={"values": {"push_daily_cap": 99}}, headers=VIA).status_code, 403)
        self.assertEqual(c.delete("/api/push/devices/1", headers=VIA).status_code, 403)
        self.assertEqual(c.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]}, headers=VIA).status_code, 200); self.assertEqual(push.devices(), [])

    def test_watches_travel_with_a_backup(self):
        self.assertIn("watches", h.api.TABLES); self.assertIn("watch_hits", h.api.TABLES)


if __name__ == "__main__":
    unittest.main()
