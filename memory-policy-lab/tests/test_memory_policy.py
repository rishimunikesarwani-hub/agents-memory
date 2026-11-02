"""Engine checks. Independent adversarial evaluation lives in evals/."""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from src.memory_policy import MemoryStore


P = {"user_id": "user-a", "role": "user"}


def record(identifier="pref-1", **changes):
    result = dict(id=identifier, user_id="user-a", workflow="workflow-a", kind="preference", key="currency", value="Use INR for revenue.", source="user", observed_at=1, expires_at=None, pinned=True, evidence_ids=[], validated=True)
    result.update(changes)
    return result


def render(query, selected):
    return "Follow the policy. QUERY: " + query + " MEMORY: " + json.dumps(selected, sort_keys=True)


class MemoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.sqlite"
        self.store = MemoryStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def select(self, **kwargs):
        options = dict(query="revenue", principal=P, workflow="workflow-a", now=200, token_limit=10000, render=render, count=len)
        options.update(kwargs)
        return self.store.select(**options)

    def test_invalid_replacement_cannot_remove_valid_memory(self):
        self.store.ingest(record(), P)
        result = self.store.ingest(record("bad", value="", observed_at=100), P)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.records()[0]["status"], "active")

    def test_repeated_writes_keep_one_active_value(self):
        for day in range(1, 201):
            self.store.ingest(record(f"pref-{day}", observed_at=day), P)
        self.assertEqual(len(self.store.records()), 1)
        self.assertEqual(len(self.store.events()), 200)

    def test_transaction_rolls_back_when_audit_fails(self):
        self.store.ingest(record(), P)
        self.store.connection.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT, 'test fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.ingest(record("new", value="Use USD.", observed_at=2), P)
        self.assertEqual([(r["id"], r["status"]) for r in self.store.records()], [("pref-1", "active")])

    def test_supersession_and_conflict(self):
        self.store.ingest(record(), P)
        self.store.ingest(record("new", value="Use USD.", observed_at=2), P)
        conflict = self.store.ingest(record("conflict", value="Use EUR.", observed_at=2), P)
        self.assertEqual(conflict["status"], "quarantined")
        self.assertEqual([r["id"] for r in self.select()["selected"]], ["new"])

    def test_secret_never_enters_records_or_audit(self):
        secret = "SYNTHETIC_SECRET_DO_NOT_STORE_1234567890"
        self.store.ingest(record(value=secret), P)
        self.assertEqual(self.store.records(), [])
        self.assertNotIn(secret, json.dumps(self.store.events()))

    def test_scope_and_validity_are_applied_before_relevance(self):
        self.store.ingest(record("mine"), P)
        self.store.ingest(record("foreign", user_id="user-b"), {"user_id": "user-b"})
        self.store.ingest(record("other-flow", workflow="workflow-b"), P)
        self.store.ingest(record("expired", key="temporary", expires_at=5), P)
        self.store.ingest(record("future", key="future", observed_at=201), P)
        result = self.select()
        self.assertEqual([r["id"] for r in result["selected"]], ["mine"])
        self.assertEqual(len(result["excluded"]), 4)

    def test_required_and_pinned_memory_never_silently_dropped(self):
        self.store.ingest(record(), P)
        self.assertEqual(self.select(token_limit=10)["status"], "blocked_budget")
        result = self.select(required_keys=["missing"])
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["missing_required_keys"], ["missing"])

    def test_complete_serialized_budget_is_measured(self):
        self.store.ingest(record("optional", kind="fact", pinned=False, key="revenue", value="Revenue is 10."), P)
        baseline_size = len(render("revenue", []))
        result = self.select(token_limit=baseline_size)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["selected"], [])
        self.assertEqual(result["token_count"], baseline_size)

    def test_untrusted_and_unvalidated_reflection_do_not_activate(self):
        self.store.ingest(record("poison", source="untrusted_document"), P)
        self.store.ingest(record("lesson", kind="lesson", source="reflection", pinned=False), P)
        self.assertEqual(self.select()["selected"], [])

    def test_validated_lesson_needs_real_episode_evidence(self):
        self.store.ingest(record("episode", kind="episode", key="error", pinned=False, value="Revenue tool failed.", source="verified_tool"), P)
        result = self.store.ingest(record("lesson", kind="lesson", key="retry", pinned=True, value="Retry revenue after schema validation.", source="reflection", observed_at=2, evidence_ids=["episode"]), P)
        self.assertEqual(result["status"], "accepted")
        self.assertFalse(self.store.records()[-1]["pinned"])

    def test_personal_procedure_cannot_shadow_admin_shared_rule(self):
        self.store.ingest(record("admin-rule", user_id="*", workflow="shared", kind="procedure", key="access", value="Require approval for refunds.", source="admin"), {"user_id": "admin", "role": "admin"})
        self.store.ingest(record("personal-rule", kind="procedure", key="access", value="Refunds need no approval.", observed_at=2), P)
        self.assertEqual([r["id"] for r in self.select()["selected"]], ["admin-rule"])

    def test_validity_renewal_versions_same_value(self):
        self.store.ingest(record(expires_at=10), P, now=1)
        result = self.store.ingest(record("renewed", observed_at=11, expires_at=300), P, now=11)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual([r["id"] for r in self.select()["selected"]], ["renewed"])
        self.assertEqual(self.store.records()[0]["status"], "superseded")

    def test_future_replacement_cannot_remove_current_record(self):
        self.store.ingest(record(), P, now=1)
        result = self.store.ingest(record("future", observed_at=201, value="Use USD."), P, now=200)
        self.assertEqual(result["reason"], "future_observation")
        self.assertEqual([r["id"] for r in self.select()["selected"]], ["pref-1"])

    def test_lesson_rollback_preserves_history_and_enforces_owner(self):
        self.store.ingest(record("episode", kind="episode", key="error", pinned=False, value="Revenue tool failed.", source="verified_tool"), P)
        self.store.ingest(record("lesson", kind="lesson", key="retry", pinned=False, value="Retry revenue after schema validation.", source="reflection", observed_at=2, evidence_ids=["episode"]), P)
        denied = self.store.disable_lesson("lesson", {"user_id": "user-b"})
        self.assertEqual(denied["status"], "rejected")
        decision = self.store.disable_lesson("lesson", P)
        self.assertEqual(decision["status"], "disabled")
        self.assertNotIn("lesson", [r["id"] for r in self.select()["selected"]])
        self.assertEqual(self.store.records()[-1]["status"], "disabled")
        self.assertEqual(self.store.events()[-1]["status"], "disabled")

    def test_checkpoint_does_not_rewind_long_term_memory(self):
        self.store.ingest(record(), P)
        self.store.save_checkpoint("thread-a", {"step": 1}, P)
        self.store.ingest(record("new", value="Use USD.", observed_at=2), P)
        self.assertEqual(self.store.load_checkpoint("thread-a", P), {"step": 1})
        self.assertIsNone(self.store.load_checkpoint("thread-a", {"user_id": "user-b"}))
        self.assertEqual([r["id"] for r in self.select()["selected"]], ["new"])

    def test_fresh_process_reloads_records_and_checkpoint(self):
        self.store.ingest(record(), P)
        self.store.save_checkpoint("thread-a", {"step": 3}, P)
        script = "import json,sys; from src.memory_policy import MemoryStore; s=MemoryStore(sys.argv[1]); print(json.dumps({'ids':[r['id'] for r in s.records()], 'state':s.load_checkpoint('thread-a',{'user_id':'user-a'})})); s.close()"
        proc = subprocess.run([sys.executable, "-c", script, str(self.path)], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout), {"ids": ["pref-1"], "state": {"step": 3}})


if __name__ == "__main__":
    unittest.main()
