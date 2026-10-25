import unittest
from types import SimpleNamespace as NS
from unittest import mock
from sw import db, llm, openrouter
from tests import helpers as h

c = h.client

CATALOG = {"data": [
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B", "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"},
     "supported_parameters": ["tools", "temperature"], "architecture": {"output_modalities": ["text"]}, "description": "big"},
    {"id": "google/gemma-3-4b-it:free", "name": "Gemma 3 4B", "context_length": 32768, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": []},
    {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000, "pricing": {"prompt": "0.0000025", "completion": "0.00001"}},
    {"id": "google/lyria-preview", "name": "Music", "context_length": 9, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["text", "audio"]}},
    {"id": "some/image-only:free", "name": "Image", "context_length": 1, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["image"]}},
    {"id": "nvidia/x-content-safety:free", "name": "Safety", "context_length": 9, "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "odd/pricing", "name": "Odd", "context_length": 5, "pricing": {"prompt": "-1", "completion": "0"}},
    {"id": "missing/pricing", "name": "None"},
]}


class CatalogTests(unittest.TestCase):
    def setUp(self): h.reset(); openrouter.reset()

    def test_only_free_text_models_longest_context_first(self):
        rows = openrouter.parse(CATALOG)
        self.assertEqual([r["id"] for r in rows], ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-4b-it:free"])
        self.assertEqual(rows[0]["model"], "openrouter/meta-llama/llama-3.3-70b-instruct:free"); self.assertTrue(rows[0]["tools"]); self.assertFalse(rows[1]["tools"])

    def test_endpoint_lists_them_and_caches(self):
        with mock.patch("sw.openrouter.httpx.get") as get:
            get.return_value = mock.Mock(json=lambda: CATALOG, raise_for_status=lambda: None)
            self.assertEqual(len(c.get("/api/openrouter/models").json()["models"]), 2)
            c.get("/api/openrouter/models"); self.assertEqual(get.call_count, 1)
            c.get("/api/openrouter/models", params={"refresh": True}); self.assertEqual(get.call_count, 2)

    def test_a_network_failure_is_a_plain_502(self):
        with mock.patch("sw.openrouter.httpx.get", side_effect=OSError("down")):
            r = c.get("/api/openrouter/models"); self.assertEqual(r.status_code, 502); self.assertIn("OpenRouter", r.json()["detail"])


class UseTests(unittest.TestCase):
    def setUp(self): h.reset(); db.set_setting("model", "openrouter/meta-llama/llama-3.3-70b-instruct:free")

    def test_openrouter_answers_chat_but_background_work_stays_local(self):
        self.assertTrue(llm.pick_model(False, "chat").startswith("openrouter/"))
        for f in ("summary", "graph", "digest", "brief"): self.assertTrue(llm.pick_model(False, f).startswith("ollama"), f)

    def test_everything_can_be_chosen(self):
        db.set_setting("cloud_scope", "everything"); self.assertTrue(llm.pick_model(False, "summary").startswith("openrouter/"))

    def test_private_and_off_the_record_never_leave(self):
        db.set_setting("cloud_scope", "everything"); self.assertTrue(llm.pick_model(True, "chat").startswith("ollama"))

    def test_the_key_is_passed_through_and_free_models_cost_nothing(self):
        db.set_setting("api_key", "sk-or-test")
        self.assertEqual(llm._kwargs("openrouter/x/y:free"), {"model": "openrouter/x/y:free", "api_key": "sk-or-test"})

    def test_a_model_without_tools_still_answers(self):
        calls = []
        def fake(**kw):
            calls.append("tools" in kw)
            if "tools" in kw: raise RuntimeError("This model does not support tool use")
            return NS(choices=[NS(message=NS(content="hi"))], usage=NS(prompt_tokens=1, completion_tokens=1))
        with mock.patch("litellm.completion", side_effect=lambda **kw: fake(**kw)):
            m = llm.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}]); self.assertEqual(m.content, "hi")
        self.assertEqual(calls, [True, False])

    def test_other_errors_are_not_retried(self):
        with mock.patch("litellm.completion", side_effect=RuntimeError("429 rate limit")) as comp:
            with self.assertRaises(RuntimeError): llm.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
        self.assertEqual(comp.call_count, 1)

    def test_test_endpoint_reports_errors_without_the_key(self):
        db.set_setting("api_key", "sk-or-secret")
        with mock.patch("sw.llm.chat", side_effect=RuntimeError("401 bad key sk-or-secret")):
            r = c.post("/api/models/test"); self.assertEqual(r.status_code, 502); self.assertNotIn("sk-or-secret", r.text)
        with mock.patch("sw.llm.chat", return_value=NS(content="ok")):
            self.assertTrue(c.post("/api/models/test").json()["ok"])


if __name__ == "__main__":
    unittest.main()
