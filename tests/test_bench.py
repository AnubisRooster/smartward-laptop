import json, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from sw import bench, db, sandbox
from tests import helpers as h
from tests.test_implications import dev, project
from tests.test_memo import answer

c = h.client
GOOD = '''import statistics
def run(sw):
    sw.generate("qwen3:0.6b", "warm up", num_predict=4)
    rates = []
    for _ in range(3):
        r = sw.generate("qwen3:0.6b", "Count to ten.", num_predict=32, seed=1)
        rates.append(r["eval_count"] / (r["eval_duration"] / 1e9))
    sw.result(metric="decode speed", value=statistics.median(rates), unit="tokens/s", baseline=None, runs=3, notes="CPU only.")
'''


class FakeOllama:
    """/api/tags, /api/generate (a fixed 20 tokens in 0.5 s) and /api/pull."""
    def __init__(self, models=("qwen3:0.6b",)):
        self.models, self.requests = list(models), []; outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _send(self, body): b = json.dumps(body).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            def do_GET(self): self._send({"models": [{"name": m} for m in outer.models] + [{"name": "nomic-embed-text:latest"}]})
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"); outer.requests.append((self.path, body))
                if self.path == "/api/pull": outer.models.append(body["model"]); self._send({"status": "success"})
                else: self._send({"response": "1 2 3", "eval_count": 20, "eval_duration": 500_000_000, "prompt_eval_count": 5, "prompt_eval_duration": 1, "load_duration": 1, "total_duration": 2})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
    def close(self): self.server.shutdown(); self.server.server_close()


def plan(**kw):
    base = {"testable": "proxy", "plan": "Measure decode speed of a small model on the CPU.", "why_not": "No GPU here.", "models": ["qwen3:0.6b", "made-up:7b"], "expected_minutes": 3, "script": GOOD}
    base.update(kw); return base


class Setup(unittest.TestCase):
    def setUp(self):
        h.reset(); bench.STATE["pulls"].clear(); self.ol = FakeOllama(); db.set_setting("ollama_base", self.ol.url)
        db.set_setting("api_key", "sk-test"); db.set_setting("model", "openrouter/openrouter/free")
        src = h.add_source("Lab blog"); self.pid = project(); self.dev = dev(h.add_article(src, "Story", "x" * 600), claim="Speculative decoding doubles decode speed.")
        self.sleep = mock.patch("sw.llm.time.sleep"); self.sleep.start()
    def tearDown(self): self.sleep.stop(); self.ol.close()

    def propose(self, **kw):
        with mock.patch("litellm.completion", return_value=answer(plan(**kw))) as comp: return bench.propose(self.dev), comp


class Checking(unittest.TestCase):
    def test_a_plain_script_passes_and_reaching_out_does_not(self):
        self.assertEqual(bench.check_script(GOOD), [])
        for src, why in (("import os\ndef run(sw): pass", "Imports os"), ("def run(sw): open('/etc/passwd')", "Uses open"), ("def run(sw): ().__class__", "Reaches into __class__"),
                         ("from subprocess import run", "Imports subprocess"), ("def go(sw): pass", "no run(sw)"), ("def run(sw: oops", "doesn't parse"), ("", "no script")):
            self.assertTrue(any(why in p for p in bench.check_script(src)), (src, bench.check_script(src)))

    def test_exactly_one_result(self):
        self.assertIn("It must report exactly one result.", bench.check_script("def run(sw):\n    sw.result(a=1)\n    sw.result(a=2)\n"))
        self.assertIn("It never reports a result.", bench.check_script("def run(sw):\n    pass\n"))

    def test_a_result_must_have_a_numeric_metric(self):
        self.assertEqual(bench.clean_result({"metric": "speed", "value": 12, "unit": "tok/s", "runs": 3})["baseline"], None)
        for bad in ({"value": 1}, {"metric": "x", "value": "fast"}, {"metric": "x", "value": True}, {"metric": "x", "value": float("nan")}, ["x"]):
            with self.assertRaises(ValueError): bench.clean_result(bad)


class Drafting(Setup):
    def test_a_plan_is_stored_for_review_with_only_known_models_and_nothing_runs(self):
        r, comp = self.propose()
        self.assertEqual(r["status"], "proposed"); self.assertEqual(r["plan"]["models"], ["qwen3:0.6b"]); self.assertEqual(r["missing"], [])

        p = comp.call_args.kwargs["messages"][0]["content"]; self.assertIn("NO GPU", p); self.assertIn("qwen3:0.6b (installed)", p); self.assertIn("Speculative decoding doubles", p)
        self.assertEqual([x for x in self.ol.requests if x[0] == "/api/generate"], [])

    def test_only_models_the_script_uses_are_listed_so_nothing_extra_is_downloaded(self):
        self.ol.models = []; r = self.propose(models=["qwen3:0.6b", "gemma3:1b"])[0]
        self.assertEqual(r["plan"]["models"], ["qwen3:0.6b"]); self.assertEqual([m["model"] for m in r["missing"]], ["qwen3:0.6b"])

    def test_untestable_claims_and_bad_scripts_are_recorded_as_such(self):
        self.assertEqual(self.propose(testable="no", script="")[0]["status"], "not_testable")
        r = self.propose(script="import os\ndef run(sw): pass")[0]; self.assertEqual(r["status"], "rejected"); self.assertIn("Imports os", r["plan"]["problems"][0])
        with self.assertRaises(ValueError): bench.start(r["id"])

    def test_a_missing_model_must_be_downloaded_first_and_only_a_listed_one(self):
        self.ol.models = []; r = self.propose()[0]
        self.assertEqual(r["missing"], [{"model": "qwen3:0.6b", "gb": 0.5, "pull": None}])
        with self.assertRaises(ValueError) as e: bench.start(r["id"])
        self.assertIn("Download qwen3:0.6b first", str(e.exception))
        with self.assertRaises(ValueError): bench.pull(r["id"], "llama3.2:3b")                  # in the catalog, but not what this test needs
        bench.pull(r["id"], "qwen3:0.6b")()
        self.assertEqual(bench.STATE["pulls"]["qwen3:0.6b"], "done"); self.assertEqual(bench.get(r["id"])["missing"], [])


class Broker(Setup):
    def test_only_approved_models_known_options_and_capped_lengths(self):
        b = bench.broker_for(["qwen3:0.6b"], max_calls=2)
        with self.assertRaises(sandbox.Refused): b({"op": "generate", "model": "llama3.2:3b", "prompt": "x"})
        with self.assertRaises(sandbox.Refused): b({"op": "pull", "model": "qwen3:0.6b"})
        with self.assertRaises(sandbox.Refused): b({"op": "generate", "model": "qwen3:0.6b", "prompt": "x", "options": {"num_gpu": 99}})
        r = b({"op": "generate", "model": "qwen3:0.6b", "prompt": "x" * 20000, "options": {"num_predict": 99999}})
        self.assertEqual(r["eval_count"], 20); sent = self.ol.requests[-1][1]; self.assertEqual(sent["options"]["num_predict"], 512); self.assertEqual(len(sent["prompt"]), 8000)
        b({"op": "generate", "model": "qwen3:0.6b", "prompt": "x"})
        with self.assertRaises(sandbox.Refused): b({"op": "generate", "model": "qwen3:0.6b", "prompt": "x"})


@unittest.skipIf(not sandbox.available(), "bubblewrap is not installed")
class Running(Setup):
    def test_an_approved_test_runs_in_the_sandbox_and_becomes_measured_evidence(self):
        r = self.propose()[0]; bench.start(r["id"]); bench.execute(r["id"])
        done = bench.get(r["id"]); self.assertEqual(done["status"], "done", done["error"]); self.assertEqual(done["result"]["value"], 40.0); self.assertEqual(done["result"]["calls"], 4)
        d = db.q("SELECT d.*, a.relevant, a.url, s.name source FROM developments d JOIN articles a ON a.id=d.article_id JOIN sources s ON s.id=a.source_id WHERE d.id=?", (done["result_dev_id"],), one=True)
        self.assertEqual((d["evidence"], d["model"], d["source"], d["relevant"], d["grounded"]), ("measured", "bench", "Test bench", 0, 1))
        self.assertIn("decode speed: 40 tokens/s over 3 runs.", d["claim"]); self.assertTrue(d["subject"].startswith("Measured here (proxy)"))
        self.assertEqual(json.loads(d["domains"]), ["Inference serving"])
        with self.assertRaises(ValueError): bench.start(r["id"])                                     # done is done
        with self.assertRaises(ValueError): bench.propose(done["result_dev_id"])                     # a measurement isn't re-measured

    def test_a_script_that_breaks_is_a_failed_run_with_its_log(self):
        r = self.propose(script="def run(sw):\n    approved = 'qwen3:0.6b'\n    print('trying')\n    sw.generate('llama3.2:3b', 'x')\n    sw.result(metric='x', value=1)\n")[0]; bench.start(r["id"]); bench.execute(r["id"])
        f = bench.get(r["id"]); self.assertEqual(f["status"], "failed"); self.assertIn("approved model", f["log"]); self.assertIsNone(f["result_dev_id"])


class Api(Setup):
    def test_the_phone_can_look_but_not_draft_approve_or_download(self):
        r = self.propose()[0]
        from tests.test_remote import VIA, turn_on, sign_in
        turn_on(); sign_in()
        self.assertEqual(c.get("/api/bench", headers=VIA).status_code, 200); self.assertEqual(c.get(f"/api/bench/{r['id']}", headers=VIA).status_code, 200)
        for path in (f"/api/bench/{r['id']}/run", f"/api/bench/{r['id']}/pull", "/api/bench"):
            self.assertEqual(c.post(path, json={"model": "qwen3:0.6b", "development_id": self.dev}, headers=VIA).status_code, 403, path)
        self.assertEqual(c.delete(f"/api/bench/{r['id']}", headers=VIA).status_code, 403)

    def test_api_states(self):
        r = self.propose()[0]
        self.assertEqual(c.post("/api/bench", json={"development_id": 999}).status_code, 404)
        with mock.patch.object(h.api, "bg", lambda fn, *a: None): self.assertTrue(c.post(f"/api/bench/{r['id']}/run").json()["started"])
        self.assertEqual(c.post(f"/api/bench/{r['id']}/run").status_code, 409); self.assertEqual(c.delete(f"/api/bench/{r['id']}").status_code, 409)
        self.assertIn("bench_runs", h.api.TABLES)


if __name__ == "__main__":
    unittest.main()
