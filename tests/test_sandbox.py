import os, unittest
from sw import db, sandbox
from tests import helpers as h   # noqa: F401  (the temporary library)

SKIP = not sandbox.available()
REAL_DB = os.path.expanduser("~/.local/share/smartward/smartward.db")


def echo(req): return {"response": "hi " + req["prompt"], "eval_count": 3}


@unittest.skipIf(SKIP, "bubblewrap is not installed")
class Sandbox(unittest.TestCase):
    def run_(self, body, broker=echo, **kw): return sandbox.run(body, broker, **kw)

    def test_a_script_asks_the_broker_and_reports_one_result(self):
        r = self.run_("def run(sw):\n    out = sw.generate('m', 'there', num_predict=3)\n    print('log line')\n    sw.result(value=out['eval_count'], said=out['response'])\n")
        self.assertIsNone(r["error"]); self.assertEqual(r["result"], {"value": 3, "said": "hi there"}); self.assertEqual(r["calls"], 1); self.assertIn("log line", r["log"])

    def test_it_cannot_read_your_files_or_the_library(self):
        r = self.run_(f"def run(sw):\n    import os\n    sw.result(home=os.path.exists({os.path.expanduser('~')!r}), db=os.path.exists({REAL_DB!r}), test_db=os.path.exists({db.DB_PATH!r}), root=sorted(os.listdir('/')))\n")
        self.assertEqual(r["result"]["home"], False); self.assertEqual(r["result"]["db"], False); self.assertEqual(r["result"]["test_db"], False)
        self.assertNotIn("home", r["result"]["root"]); self.assertNotIn("etc", r["result"]["root"])

    def test_it_has_no_network_not_even_the_model_server(self):
        r = self.run_("def run(sw):\n    import socket\n    out = {}\n    for host, port in (('127.0.0.1', 11434), ('127.0.0.1', 8000), ('1.1.1.1', 443)):\n"
                      "        try: socket.create_connection((host, port), timeout=2); out[f'{host}:{port}'] = 'open'\n"
                      "        except OSError as e: out[f'{host}:{port}'] = 'blocked'\n    sw.result(**out)\n")
        self.assertEqual(set(r["result"].values()), {"blocked"}, r["result"])

    def test_it_cannot_write_outside_its_own_tmp_and_the_script_is_read_only(self):
        r = self.run_("def run(sw):\n    out = {}\n    for p in ('/usr/x', '/work/bench.py', '/tmp/ok'):\n        try: open(p, 'w').write('x'); out[p] = 'written'\n        except OSError: out[p] = 'refused'\n    sw.result(**out)\n")
        self.assertEqual(r["result"], {"/usr/x": "refused", "/work/bench.py": "refused", "/tmp/ok": "written"})

    def test_a_runaway_script_is_stopped(self):
        r = self.run_("def run(sw):\n    while True: pass\n", timeout=3)
        self.assertIsNone(r["result"]); self.assertIn("Stopped after 3 seconds", r["error"])

    def test_memory_is_limited(self):
        r = self.run_("def run(sw):\n    x = bytearray(2 * 1024**3)\n    sw.result(ok=True)\n", memory_mb=256)
        self.assertIsNone(r["result"]); self.assertIn("MemoryError", r["log"])

    def test_only_a_proper_result_counts(self):
        self.assertIn("without a result", self.run_("def run(sw):\n    print('@@result {\"forged\": 1}')\n")["error"])     # prints go to the log, not the protocol
        self.assertIn("more than one", self.run_("def run(sw):\n    sw.result(a=1); sw.result(a=2)\n")["error"])
        self.assertIn("without a result", self.run_("def run(sw):\n    raise ValueError('boom')\n")["error"])

    def test_a_refusal_reaches_the_script_as_an_error(self):
        def no(req): raise sandbox.Refused("Only the approved model.")
        r = self.run_("def run(sw):\n    try: sw.generate('other', 'x')\n    except RuntimeError as e: sw.result(error=str(e))\n", broker=no)
        self.assertEqual(r["result"], {"error": "Only the approved model."})


if __name__ == "__main__":
    unittest.main()
