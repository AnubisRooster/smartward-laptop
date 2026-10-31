import time, unittest
from sw import maps, rules
from tests import helpers as h  # noqa: F401  (the temporary library)

GOOD = """@pattern agent_platform
Developers (actor): developers

[On-prem data center]
Coding agent (agent): claude code, codex
Harness (service): agent harness, sandbox, gvisor
Repo and CI (service): github, ci/cd, pull request
Job queue (service): temporal, queue
Control plane (service): kubernetes
Model router (gateway): routing, router
Guardrails (service): nemo guardrails, llama guard, dlp
Identity & policy (service): oidc, opa, rbac
Secrets (service): vault
Observability (service): opentelemetry, langfuse, cost
Audit log (datastore): audit, siem
Tool registry (datastore): mcp, tool registry
Self-evolving skills (service): skill evolution
Evaluation (service): evals
Ingestion (service): connectors, embeddings
Knowledge store (datastore): vector database, rag
vLLM serving (model): vllm
GPUs (infra): h100

[AWS]
Bedrock (external): bedrock

Developers -> Job queue: submits tasks (HTTPS)
Job queue -> Coding agent: dispatches tasks
Identity & policy => Job queue: authenticates
Identity & policy => Model router: authorizes
Identity & policy => Tool registry: grants tools
Coding agent -> Harness: runs code in sandbox
Coding agent -> Repo and CI: opens pull requests
Coding agent -> Guardrails: checks prompts and outputs
Guardrails -> Model router: forwards prompts
Coding agent -> Tool registry: discovers tools (MCP)
Coding agent -> Knowledge store: retrieves context
Coding agent -> Observability: traces
Model router -> vLLM serving: inference (OpenAI API)
Model router -> Bedrock: inference after redaction (Bedrock API)
Model router -> Observability: tokens and cost
Model router -> Audit log: records calls
Model router -> Secrets: reads provider keys
Control plane => vLLM serving: schedules
vLLM serving -> GPUs: runs on
Self-evolving skills -> Evaluation: candidate skills
Evaluation => Tool registry: approves skills
Ingestion -> Knowledge store: indexes documents
"""


def score(text, **kw): return rules.score(maps.parse(text), **kw)


def failed(text): return {r["id"]: r["detail"] for r in score(text)["rules"] if not r["ok"]}


class Rules(unittest.TestCase):
    def test_a_well_built_agent_platform_meets_every_rule(self):
        self.assertEqual(failed(GOOD), {}); self.assertEqual(score(GOOD)["missing"], [])

    def test_backwards_and_misattributed_arrows_are_caught(self):
        bad = GOOD + "Knowledge store -> Coding agent: pushes context\nCoding agent -> Developers: asks\nAudit log => Model router: governs\nGPUs -> Control plane: sends data\n"
        f = failed(bad)
        self.assertIn("Knowledge store", f["C1"]); self.assertIn("Developers", f["C2"]); self.assertIn("Audit log", f["C4"]); self.assertIn("GPUs", f["C3"])

    def test_each_practice_fails_when_its_part_or_path_is_missing(self):
        cases = {"S2": ("Harness (service): agent harness, sandbox, gvisor", "Harness (service): agent harness"),
                 "S3": ("Secrets (service): vault", "Keys (service): keys"),
                 "S5": ("Guardrails (service): nemo guardrails, llama guard, dlp", "Proxy layer (service): envoy"),
                 "G1": ("Audit log (datastore): audit, siem", "History (datastore): history"),
                 "G3": ("Repo and CI (service): github, ci/cd, pull request", "Workspace (service): files"),
                 "R2": ("Job queue (service): temporal, queue", "Front door (service): door")}
        for rid, (old, new) in cases.items():
            text = GOOD.replace(old, new).replace(old.split(" (")[0], new.split(" (")[0])
            self.assertIn(rid, failed(text), rid)

    def test_new_skills_must_pass_the_evaluation_gate(self):
        bypass = GOOD + "Self-evolving skills -> Tool registry: registers skills\n"
        self.assertIn("G2", failed(bypass))

    def test_rules_that_do_not_apply_do_not_count(self):
        sc = score("Users (actor): u\nWeb app (app): web\nDatabase (datastore): postgres\nUsers -> Web app: browses\nWeb app -> Database: queries")
        ids = {r["id"] for r in sc["rules"]}
        self.assertNotIn("S2", ids); self.assertNotIn("G2", ids); self.assertNotIn("R1", ids); self.assertIn("C1", ids)

    def test_a_waived_rule_counts_as_met_and_is_listed(self):
        text = "@waive S3: keys are issued by the platform team's vault\n" + GOOD.replace("Secrets (service): vault\n", "").replace("Model router -> Secrets: reads provider keys\n", "")
        self.assertNotIn("S3", failed(text)); self.assertEqual(score(text)["waived"][0]["id"], "S3")
        m = maps.parse(text); self.assertIn("@waive S3: keys are issued", maps.to_text(m))
        self.assertIn("rule id", maps.parse("@waive nonsense")["problems"][0])

    def test_the_total_weights_the_parts(self):
        sc = score(GOOD, project={"name": "Platform", "goal": "It will include a coding agent, harness and model router."})
        self.assertEqual(sc["parts"]["fidelity"], 100); self.assertEqual(sc["total"], 100)
        worse = score(GOOD.replace("Secrets (service): vault", "Keys (service): keys").replace("Secrets", "Keys"))
        self.assertLess(worse["total"], 100); self.assertLess(worse["parts"]["practice"], 100)

    def test_the_brief_components_are_read_and_found(self):
        p = {"name": "AI Platform with coding agent, harness, control plane, and self evolving skills",
             "goal": "Create an enterprise AI platform. Components will include a coding agent and harness, control plane, hybrid agent development kit, self evolving skills, model router, and containerized applications."}
        self.assertEqual(rules.brief_components(p), ["coding agent", "harness", "control plane", "hybrid agent development kit", "self evolving skills", "model router", "containerized applications"])
        sc = score(GOOD, project=p)
        missing = [b["component"] for b in sc["brief"] if not b["present"]]
        self.assertEqual(missing, ["hybrid agent development kit", "containerized applications"]); self.assertLess(sc["parts"]["fidelity"], 100)

    def test_every_rule_names_its_source_why_and_fix(self):
        for rid, area, w, title, why, fix, ref, fn in rules.RULES:
            self.assertTrue(why and fix and ref and title, rid); self.assertIn(area, rules.AREAS); self.assertIn(w, (1, 2, 3))

    def test_the_reviewers_answers_become_partial_credit_and_constraints(self):
        m = maps.parse(GOOD)
        rev = maps._clean_review({"implausible": [{"from": "Coding agent", "to": "Harness", "why": "x"}, {"from": "Ghost", "to": "Harness", "why": "made up"}],
                                  "bad_protocols": [], "constraints": [{"text": "Supports Azure", "met": False, "why": "no Azure"}, "junk"]}, m)
        self.assertEqual(len(rev["implausible"]), 1); self.assertEqual(len(rev["constraints"]), 1)       # unknown parts and junk dropped
        sc = rules.score(m, {"name": "x", "goal": ""}, None, rev)
        j1 = next(r for r in sc["rules"] if r["id"] == "J1"); self.assertFalse(j1["ok"]); self.assertGreater(j1["credit"], 0.8)
        self.assertEqual(sc["parts"]["fidelity"], 0)


if __name__ == "__main__":
    unittest.main()
