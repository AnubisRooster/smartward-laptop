import unittest
from sw import db, signals
from tests import helpers as h

c = h.client
NOW = 1_800_000_000.0
D = signals.DAY


def src(name, kind="rss"): return h.add_source(name, kind=kind)


def art(source, title, days_ago, theme_ids=(), graphed=1, teaser=""):
    a = db.x("INSERT INTO articles(source_id,url,title,teaser,published,stage,relevant,relevance,graph_done,created) VALUES(?,?,?,?,?,'done',1,0.5,?,?)",
             (source, f"https://x/{title}-{days_ago}-{db.now()}", title, teaser, NOW - days_ago * D, graphed, NOW))
    for t in theme_ids: db.x("INSERT INTO mentions(article_id,theme_id,ts,source_kind) VALUES(?,?,?,'article')", (a, t, NOW - days_ago * D))
    return a


def theme(name, typ="technique"): return db.x("INSERT INTO themes(name,key,type,created) VALUES(?,?,?,?)", (name, name.lower(), typ, NOW))


def background(sources, per_week=6, weeks=8, theme_ids=()):
    """Steady filler so every source covers the whole baseline and the volume is known."""
    for s in sources:
        for w in range(weeks):
            for k in range(per_week): art(s, f"filler {s} {w} {k}", w * 7 + 0.5 + k * 0.3, theme_ids)


class Signals(unittest.TestCase):
    def setUp(self):
        h.reset(); self.s1, self.s2, self.s3 = src("Blog A"), src("Blog B"), src("OpenAI")
        background([self.s1, self.s2, self.s3])
        self.dom = {"name": "Test", "keywords": []}

    def run_(self, domain=None): return signals.analyse(domain or self.dom, NOW)

    def names(self, r, key): return [x["name"] for x in r[key]]

    def test_a_new_idea_from_two_sources_is_emerging(self):
        t = theme("EAGLE-4")
        for i, s in enumerate((self.s1, self.s2, self.s1, self.s2)): art(s, f"eagle {i}", 1 + i, [t])
        r = self.run_(); self.assertIn("EAGLE-4", self.names(r, "emerging"))

    def test_a_new_idea_from_a_single_source_is_not_called_emerging(self):
        t = theme("Lonely idea")
        for i in range(4): art(self.s1, f"lonely {i}", 1 + i, [t])
        self.assertNotIn("Lonely idea", self.names(self.run_(), "emerging"))

    def test_a_topic_that_speeds_up_is_rising_and_one_that_stops_is_cooling(self):
        up, down = theme("Prefix caching"), theme("Old thing")
        for i in range(2): art(self.s1, f"pc old {i}", 20 + i, [up])
        for i in range(8): art(self.s2, f"pc new {i}", 0.5 + i, [up])
        for i in range(12): art(self.s1, f"old {i}", 16 + i * 2, [down])
        r = self.run_(); self.assertIn("Prefix caching", self.names(r, "rising")); self.assertIn("Old thing", self.names(r, "cooling"))

    def test_a_busier_week_overall_does_not_make_everything_look_hot(self):
        t = theme("Steady theme")
        for w in range(8):
            for k in range(2): art(self.s1, f"steady {w} {k}", w * 7 + 1 + k, [t])
        r = self.run_(); self.assertNotIn("Steady theme", self.names(r, "rising") + self.names(r, "emerging"))

    def test_generic_themes_are_ignored(self):
        ai = theme("AI", "concept")
        for i in range(8): art(self.s1, f"ai {i}", 0.5 + i, [ai])
        r = self.run_(); self.assertEqual([x for x in r["rising"] + r["emerging"] if x["name"] == "AI"], [])

    def test_two_separate_clusters_that_suddenly_meet_are_a_bridge(self):
        a = [theme(f"A{i}") for i in range(3)]; b = [theme(f"B{i}") for i in range(3)]
        for i in range(3): art(self.s1, f"clusterA {i}", 20 + i, a); art(self.s2, f"clusterB {i}", 25 + i, b)
        for i in range(2): art(self.s3, f"meet {i}", 1 + i, [a[0], b[0]])
        r = self.run_(); pair = [x for x in r["converging"] if {x["a"], x["b"]} == {"A0", "B0"}]
        self.assertTrue(pair and pair[0]["bridge"] and pair[0]["together"] == 2)

    def test_a_pair_that_always_appeared_together_is_not_converging(self):
        x, y = theme("X"), theme("Y")
        for i in range(3): art(self.s1, f"xy old {i}", 20 + i, [x, y])
        for i in range(2): art(self.s1, f"xy new {i}", 1 + i, [x, y])
        self.assertEqual([p for p in self.run_()["converging"] if {p["a"], p["b"]} == {"X", "Y"}], [])

    def test_the_adoption_ladder_orders_paper_release_lab_blog(self):
        arx, gh = src("arXiv: x", "arxiv"), src("org/repo releases", "github")
        t = theme("Medusa")
        art(arx, "paper", 30, [t]); art(gh, "release", 12, [t]); art(self.s3, "lab post", 5, [t]); art(self.s1, "blog take", 2, [t])
        art(self.s1, "blog take 2", 1, [t]); art(self.s2, "blog take 3", 1, [t])
        arts, _, by_article = signals.load(NOW); ladder = signals.ladder(t, by_article, arts, {i for i in arts if arts[i]["graph_done"]})
        self.assertEqual([s["stage"] for s in ladder["stages"]], ["paper", "release", "lab", "blog"]); self.assertEqual(ladder["furthest"], "blog"); self.assertIsNone(ladder["next"])

    def test_a_source_that_only_just_started_is_left_out_of_rate_comparisons(self):
        new = src("Brand new feed")
        for i in range(10): art(new, f"new feed {i}", 0.2 + i * 0.5)
        arts, _, _ = signals.load(NOW); t = signals.source_totals(arts, NOW)
        self.assertFalse(t[new]["eligible"]); self.assertTrue(t[self.s1]["eligible"])

    def test_a_flood_from_a_brand_new_feed_does_not_look_like_a_trend(self):
        new = src("Flood feed")
        for i in range(30): art(new, f"Speculative decoding flood {i}", 0.1 + i * 0.3)           # appears out of nowhere, only covers the last 9 days
        r = self.run_({"name": "Spec", "keywords": ["speculative decoding"]})
        self.assertEqual(r["momentum"]["recent"], 30); self.assertNotIn(r["momentum"]["label"], ("rising", "emerging"))     # it can't be compared, so it isn't claimed

    def test_a_source_with_only_part_of_the_baseline_is_judged_over_that_part(self):
        short = src("Capped feed")
        for w in range(3):                                          # 3 weeks of history, a steady 1 in 2 about the topic
            for k in range(8): art(short, f"cap {w} {k} " + ("speculative decoding" if k % 2 == 0 else "other"), w * 7 + 15 + k * 0.5)
        for k in range(8): art(short, f"cap now {k} " + ("speculative decoding" if k % 2 == 0 else "other"), 0.5 + k)
        arts, _, _ = signals.load(NOW); self.assertTrue(signals.source_totals(arts, NOW)[short]["eligible"])
        r = self.run_({"name": "Spec", "keywords": ["speculative decoding"]}); self.assertNotEqual(r["momentum"]["label"], "rising")       # same share as before: steady

    def test_domain_keywords_match_whole_words_only(self):
        rx = signals.keyword_regex(["eagle", "kv cache", "llama.cpp"])
        self.assertTrue(rx.search("eagle decoding is fast")); self.assertFalse(rx.search("a beagle ran")); self.assertTrue(rx.search("the kv cache grows")); self.assertTrue(rx.search("run llama.cpp locally"))

    def test_domain_momentum_uses_the_keywords_even_when_nothing_is_graphed(self):
        for i in range(8): art((self.s1, self.s2)[i % 2], f"Speculative decoding result {i}", 0.5 + i, graphed=0)
        r = self.run_({"name": "Spec", "keywords": ["speculative decoding"]})
        self.assertEqual(r["momentum"]["recent"], 8); self.assertEqual(r["momentum"]["label"], "emerging"); self.assertGreater(sum(r["weekly"]), 7)

    def test_one_source_alone_can_make_a_topic_rise_but_not_emerge(self):
        for i in range(8): art(self.s1, f"Speculative decoding result {i}", 0.5 + i, graphed=0)
        self.assertEqual(self.run_({"name": "Spec", "keywords": ["speculative decoding"]})["momentum"]["label"], "rising")

    def test_the_answer_says_how_much_data_it_rests_on(self):
        r = self.run_(); self.assertEqual(r["coverage"]["sources_comparable"], 3); self.assertTrue(r["coverage"]["provisional"])      # three sources is too few to trust a trend
        background([src("Blog D"), src("Blog E")]); r = self.run_(); self.assertEqual(r["coverage"]["sources_comparable"], 5); self.assertFalse(r["coverage"]["provisional"])
        h.reset(); s = src("Tiny"); art(s, "one", 1); self.assertTrue(signals.analyse(self.dom, NOW)["coverage"]["provisional"])

    def test_default_domains_are_seeded_once_and_editable(self):
        names = [d["name"] for d in signals.domains()]; self.assertIn("KV cache", names); self.assertEqual(len(signals.domains()), len(names))


if __name__ == "__main__":
    unittest.main()


class SignalsApi(unittest.TestCase):
    def setUp(self): h.reset()

    def test_signals_for_all_domains_and_for_one(self):
        d = c.get("/api/domains").json(); self.assertGreaterEqual(len(d), 5)
        r = c.get("/api/signals"); self.assertEqual(r.status_code, 200); self.assertEqual(len(r.json()["domains"]), len(d))
        one = c.get("/api/signals", params={"domain": d[0]["id"]}).json(); self.assertEqual(one["domains"][0]["domain"], d[0]["name"])
        self.assertEqual(c.get("/api/signals", params={"domain": 9999}).status_code, 404)

    def test_domains_can_be_added_edited_and_removed(self):
        self.assertEqual(c.post("/api/domains", json={"name": "x", "keywords": []}).status_code, 400)
        did = c.post("/api/domains", json={"name": "Robotics", "keywords": ["robot", "manipulation"]}).json()["id"]
        c.put(f"/api/domains/{did}", json={"keywords": ["robot arm"]}); self.assertEqual([x for x in c.get("/api/domains").json() if x["id"] == did][0]["keywords"], ["robot arm"])
        self.assertEqual(c.put(f"/api/domains/{did}", json={"keywords": []}).status_code, 400)
        c.delete(f"/api/domains/{did}"); self.assertNotIn(did, [x["id"] for x in c.get("/api/domains").json()])

    def test_a_signed_in_phone_may_read_signals_but_not_edit_domains(self):
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get("/api/signals", headers=VIA).status_code, 200); self.assertEqual(c.get("/api/domains", headers=VIA).status_code, 200)
        self.assertEqual(c.post("/api/domains", json={"name": "x", "keywords": ["y"]}, headers=VIA).status_code, 403)


class Refinements(unittest.TestCase):
    def setUp(self):
        h.reset(); self.s1, self.s2, self.s3 = src("Blog A"), src("Blog B"), src("OpenAI"); background([self.s1, self.s2, self.s3])

    def test_a_model_and_its_longer_name_are_not_a_convergence(self):
        a, b = theme("GPT-6", "model"), theme("GPT-6 Astra", "model"); other = [theme("Other1"), theme("Other2")]
        for i in range(3): art(self.s1, f"base {i}", 20 + i, [a, other[0]]); art(self.s2, f"base2 {i}", 25 + i, [b, other[1]])
        for i in range(2): art(self.s3, f"meet {i}", 1 + i, [a, b])
        self.assertEqual([p for p in signals.analyse({"name": "T", "keywords": []}, NOW)["converging"] if {p["a"], p["b"]} == {"GPT-6", "GPT-6 Astra"}], [])

    def test_the_top_themes_always_show_what_the_domain_is_about_even_when_nothing_is_rising(self):
        t = theme("Steady topic")
        for w in range(8):
            for k in range(2): art(self.s1, f"steady {w} {k}", w * 7 + 1 + k, [t])
        r = signals.analyse({"name": "T", "keywords": []}, NOW)
        self.assertIn("Steady topic", [x["name"] for x in r["top"]]); self.assertEqual([x for x in r["top"] if x["name"] == "Steady topic"][0]["label"], "steady")


class SameThingDifferentSpelling(unittest.TestCase):
    def test_canonical_names(self):
        for a, b in (("KV cache", "Key-Value (KV) cache"), ("Large Language Models", "large language model"), ("vLLM", "VLLM"), ("Speculative decoding", "speculative  Decoding")): self.assertEqual(signals.canon(a), signals.canon(b), (a, b))
        for a, b in (("Llama 3", "Llama 3.1"), ("GPT-6", "GPT-6 Astra"), ("Claude", "Claude Opus")): self.assertNotEqual(signals.canon(a), signals.canon(b), (a, b))

    def test_variants_are_counted_as_one_theme_and_generic_ones_are_hidden(self):
        h.reset(); s1, s2, s3 = src("Blog A"), src("Blog B"), src("Blog C"); background([s1, s2, s3])
        names = ["KV cache", "Key-Value (KV) cache", "KV caches"]; ts_ = [theme(n) for n in names]; llm_ = [theme("Large Language Models"), theme("Large Language Model")]
        for i in range(3): art((s1, s2, s3)[i], f"kv {i}", 1 + i, [ts_[i]] + [llm_[i % 2]])
        r = signals.analyse({"name": "T", "keywords": []}, NOW); top = {x["name"]: x for x in r["top"]}
        self.assertEqual(len([n for n in top if signals.canon(n) == "kv cache"]), 1); self.assertEqual(sum(x["recent"] for n, x in top.items() if signals.canon(n) == "kv cache"), 3)
        self.assertFalse([n for n in top if signals.canon(n) == "large language model"])
