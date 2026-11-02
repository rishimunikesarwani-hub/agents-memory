"""Offline retrieval wiring evaluation with explicit, hand-authored vectors."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.evaluate_policy import ADMIN, PRINCIPAL, byte_count, candidate, default_render
from src.hybrid_retrieval import HybridConfig, HybridRetriever, record_text
from src.memory_policy import MemoryStore

QUERY = "late payouts"
TARGET_ID = "settlement-delay"
VECTOR_SOURCE = "hand_authored_test_fixture"
WORKFLOW = "workflow-a"


class HandAuthoredEmbedder:
    """Return listed fixture vectors. This class does not call a model."""

    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [list(self.vectors[text]) for text in texts]


def fixture_config():
    return HybridConfig(provider="fixture", model="hand-authored-v1", dimensions=3)


def _metrics(selected_ids):
    relevant = int(TARGET_ID in selected_ids)
    return {
        "relevant_ids": [TARGET_ID],
        "precision": relevant / len(selected_ids) if selected_ids else 0.0,
        "recall": float(relevant),
        "label_source": "hand_authored_fixture_expectations",
    }


def _snapshot(result):
    snapshot = json.loads(json.dumps(result, allow_nan=False))
    snapshot["selected_ids"] = [record["id"] for record in snapshot["selected"]]
    snapshot["context"] = snapshot["prompt"]
    snapshot["fixture_metrics"] = _metrics(snapshot["selected_ids"])
    if "ranked" in snapshot["retrieval_details"]:
        snapshot["scores"] = snapshot["retrieval_details"]["ranked"]
    else:
        terms = set(QUERY.split())
        snapshot["scores"] = [
            {"id": record["id"], "lexical_score": len(terms & set(re.findall(
                r"[a-z0-9]+", (record["key"] + " " + record["value"]).casefold()
            )))}
            for record in snapshot["selected"]
        ]
    return snapshot


def run_hybrid_evaluation(root=ROOT, count=byte_count, render=default_render):
    """Return a JSON-safe report. Temporary databases leave no persisted state."""
    fixtures = [
        candidate(TARGET_ID, key="settlement_timing", value="Settlement delays occur after bank holidays."),
        candidate("lexical-distractor", key="fee_archives", value="Late fee invoices are archived every Friday."),
        candidate("unrelated", key="equipment_warranty", value="Kitchen equipment warranty lasts two years."),
        candidate("foreign-user", user_id="bob", value="Foreign account settlement details."),
        candidate("foreign-workflow", workflow="workflow-b", value="Other workflow settlement details."),
        candidate("expired", expires_at=2, value="Expired settlement details."),
        candidate("quarantined", source="untrusted_document", value="Untrusted settlement details."),
    ]
    record_vectors = {record["id"]: [1.0, 0.0, 0.0] for record in fixtures}
    record_vectors["lexical-distractor"] = [0.0, 1.0, 0.0]
    record_vectors["unrelated"] = [0.0, 0.0, 1.0]
    vectors = {record_text(record): record_vectors[record["id"]] for record in fixtures}
    vectors[QUERY] = [1.0, 0.0, 0.0]
    embedder = HandAuthoredEmbedder(vectors)
    with tempfile.TemporaryDirectory(prefix="hybrid-fixture-eval-") as directory:
        with MemoryStore(Path(directory) / "memory.sqlite3") as store:
            writes = [store.ingest(record, ADMIN) for record in fixtures]
            arguments = {
                "query": QUERY, "principal": PRINCIPAL, "workflow": WORKFLOW, "now": 10,
                "token_limit": 10000, "render": render, "count": count,
            }
            before = _snapshot(store.select(**arguments))
            # This flag permits fixture execution. The injected embedder only reads the listed vectors.
            with HybridRetriever(Path(directory) / "vectors.sqlite3", config=fixture_config(),
                                 embedder=embedder, allow_remote=True) as retriever:
                after = _snapshot(store.select(**arguments, hybrid_retriever=retriever))
            persisted_records = store.records()

    embedded_texts = [text for call in embedder.calls for text in call]
    forbidden_ids = {"foreign-user", "foreign-workflow", "expired", "quarantined"}
    forbidden_texts = {record_text(record) for record in fixtures if record["id"] in forbidden_ids}
    target = next(record for record in fixtures if record["id"] == TARGET_ID)
    checks = {
        "target_has_zero_lexical_overlap": not set(QUERY.split()) & set(re.findall(
            r"[a-z0-9]+", target["key"] + " " + target["value"].casefold())),
        "lexical_baseline_misses_paraphrase": before["selected_ids"] == ["lexical-distractor"],
        "hybrid_retrieves_paraphrase": set(after["selected_ids"]) == {TARGET_ID, "lexical-distractor"},
        "unrelated_record_is_excluded": "unrelated" not in after["selected_ids"],
        "policy_filters_apply_before_embedding": not forbidden_texts.intersection(embedded_texts),
        "forbidden_records_are_not_selected": not forbidden_ids.intersection(after["selected_ids"]),
        "both_requests_are_ready": before["status"] == after["status"] == "ready",
        "complete_context_fits_budget": all(view["token_count"] <= view["token_limit"] for view in (before, after)),
        "semantic_branch_ran": after["retrieval_details"]["semantic_status"] == "ready",
    }
    return {
        "suite": "offline-hybrid-retrieval-wiring",
        "status": "passed" if all(checks.values()) else "failed",
        "project_root": str(Path(root).resolve()),
        "vector_source": VECTOR_SOURCE,
        "live_api_calls": 0,
        "query": QUERY,
        "target_id": TARGET_ID,
        "records": persisted_records,
        "write_results": writes,
        "fixture_vectors": {"query": vectors[QUERY], "records": record_vectors},
        "embedding_input_texts": embedded_texts,
        "count_method": "utf8_bytes_not_model_tokens" if count is byte_count else getattr(count, "__name__", "provided_counter"),
        "before": before,
        "after": after,
        "checks": checks,
        "evidence_boundary": (
            "Hand-authored vectors test ranking, filtering, and budget integration. "
            "They do not measure an embedding model's semantic quality or validate the cosine threshold. "
            "The lexical distractor remains selected. These fixture metrics do not establish production precision or recall."
        ),
    }


if __name__ == "__main__":
    report = run_hybrid_evaluation()
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    sys.exit(0 if report["status"] == "passed" else 1)
