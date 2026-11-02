"""Offline tests of the policy boundary around hybrid retrieval."""

import json
from unittest.mock import MagicMock

import openai
import pytest

from evals.evaluate_hybrid import QUERY, TARGET_ID, fixture_config, run_hybrid_evaluation
from evals.evaluate_policy import ADMIN, PRINCIPAL, byte_count, candidate, default_render
from src.hybrid_retrieval import HybridRetriever, record_text
from src.memory_policy import MemoryStore


class RecordingEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


@pytest.fixture(autouse=True)
def forbid_api_clients(monkeypatch):
    """An accidental SDK client creation fails before any network request."""
    factory = MagicMock(side_effect=AssertionError("This suite must not create an API client"))
    monkeypatch.setattr(openai, "OpenAI", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-noncredential")
    yield factory
    factory.assert_not_called()


def select(store, **overrides):
    arguments = {
        "query": QUERY, "principal": PRINCIPAL, "workflow": "workflow-a", "now": 10,
        "token_limit": 10000, "render": default_render, "count": byte_count,
    }
    arguments.update(overrides)
    return store.select(**arguments)


def ingest(store, record, expected="accepted"):
    result = store.ingest(record, ADMIN)
    assert result["status"] == expected, result


@pytest.mark.parametrize("count", [byte_count, len])
def test_fixture_demo_reports_paraphrase_and_precise_evidence_boundary(tmp_path, count):
    report = run_hybrid_evaluation(tmp_path, count, default_render)
    assert report["status"] == "passed", report["checks"]
    assert report["vector_source"] == "hand_authored_test_fixture"
    assert report["live_api_calls"] == 0
    assert report["before"]["selected_ids"] == ["lexical-distractor"]
    assert set(report["after"]["selected_ids"]) == {TARGET_ID, "lexical-distractor"}
    assert report["before"]["fixture_metrics"]["recall"] == 0.0
    assert report["after"]["fixture_metrics"]["recall"] == 1.0
    assert report["after"]["fixture_metrics"]["precision"] == 0.5
    ranking = {item["id"]: item for item in report["after"]["retrieval_details"]["ranked"]}
    assert ranking[TARGET_ID]["lexical_score"] == 0
    assert ranking[TARGET_ID]["cosine"] == pytest.approx(1.0)
    assert "do not measure" in report["evidence_boundary"]
    json.dumps(report, allow_nan=False)


def test_scope_validity_status_and_authority_filter_before_embedding(tmp_path):
    allowed = [
        candidate("own", value="Own account detail."),
        candidate("admin-procedure", user_id="*", workflow="shared", kind="procedure",
                  key="safety-rule", source="admin", value="Administrator procedure."),
        candidate("specific-fact", key="scope-choice", value="Specific fact."),
        candidate("current", key="revision", observed_at=2, value="Current detail."),
    ]
    excluded = [
        candidate("foreign-user", user_id="bob", value="Foreign user detail."),
        candidate("foreign-workflow", workflow="workflow-b", value="Foreign workflow detail."),
        candidate("expired", expires_at=2, value="Expired detail."),
        candidate("future", observed_at=20, value="Future detail."),
        candidate("untrusted", source="untrusted_document", value="Untrusted detail."),
        candidate("lower-procedure", kind="procedure", key="safety-rule", value="Lower authority procedure."),
        candidate("shared-fact", user_id="*", workflow="shared", key="scope-choice", value="Shared fact."),
        candidate("superseded", key="revision", value="Previous detail."),
    ]
    embedder = RecordingEmbedder()
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        for record in excluded + allowed:
            ingest(store, record, "quarantined" if record["id"] == "untrusted" else "accepted")
        with HybridRetriever(tmp_path / "vectors.sqlite3", config=fixture_config(), embedder=embedder,
                             allow_remote=True) as retriever:
            result = select(store, hybrid_retriever=retriever)
    embedded = {text for batch in embedder.calls for text in batch}
    assert embedded == {QUERY, *(record_text(record) for record in allowed)}
    assert {record["id"] for record in result["selected"]} == {record["id"] for record in allowed}
    reasons = {record["id"]: record["reason"] for record in result["excluded"]}
    assert reasons["foreign-user"] == "outside_user_scope"
    assert reasons["foreign-workflow"] == "outside_workflow_scope"
    assert reasons["expired"] == "expired"
    assert reasons["future"] == "future_dated"
    assert reasons["untrusted"] == "quarantined"
    assert reasons["superseded"] == "superseded"
    assert reasons["lower-procedure"] == reasons["shared-fact"] == "shadowed_by_specific_scope"


def test_mandatory_records_precede_embedding_and_full_prompt_budget_holds(tmp_path):
    mandatory = [
        candidate("required", key="account_id", value="Account number 42."),
        candidate("pinned-preference", kind="preference", pinned=True, value="Use concise replies."),
        candidate("pinned-procedure", kind="procedure", pinned=True, value="Check evidence before replying."),
    ]
    optional = candidate("optional", value=("Settlement details " * 60).strip())
    embedder = RecordingEmbedder()
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        for record in mandatory + [optional]:
            ingest(store, record)
        mandatory_result = select(store, required_keys=["account_id"])
        limit = mandatory_result["token_count"]
        with HybridRetriever(tmp_path / "vectors.sqlite3", config=fixture_config(), embedder=embedder,
                             allow_remote=True) as retriever:
            result = select(store, required_keys=["account_id"], token_limit=limit, hybrid_retriever=retriever)
    assert result["status"] == "ready"
    assert {record["id"] for record in result["selected"]} == {record["id"] for record in mandatory}
    assert result["token_count"] == byte_count(result["prompt"]) == limit
    assert any(item["id"] == "optional" and item["reason"] == "budget" for item in result["excluded"])
    assert {text for batch in embedder.calls for text in batch} == {QUERY, record_text(optional)}


@pytest.mark.parametrize("gate, expected", [("missing", "insufficient_evidence"), ("overflow", "blocked_budget")])
def test_mandatory_failure_skips_ranker_and_embedding(tmp_path, gate, expected):
    embedder = RecordingEmbedder()
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        ingest(store, candidate("mandatory", kind="preference", pinned=True, value="Required response style."))
        ingest(store, candidate("optional", value="Late payouts reference."))
        with HybridRetriever(tmp_path / "vectors.sqlite3", config=fixture_config(), embedder=embedder,
                             allow_remote=True) as retriever:
            rank = MagicMock(wraps=retriever.rank)
            retriever.rank = rank
            arguments = {"required_keys": ["absent"]} if gate == "missing" else {"token_limit": 1}
            result = select(store, hybrid_retriever=retriever, **arguments)
            rank.assert_not_called()
    assert result["status"] == expected
    assert result["retrieval"] == "not_run"
    assert embedder.calls == []


@pytest.mark.parametrize("identifiers", [["foreign"], ["allowed", "allowed"]])
def test_ranker_cannot_return_unauthorized_or_duplicate_ids(tmp_path, identifiers):
    class InvalidRanker:
        def rank(self, query, records, principal, workflow):
            assert [record["id"] for record in records] == ["allowed"]
            return {"mode": "hybrid", "semantic_status": "ready", "ranked": [
                {"id": identifier, "score": 1.0} for identifier in identifiers
            ]}

    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        ingest(store, candidate("allowed"))
        ingest(store, candidate("foreign", user_id="bob"))
        with pytest.raises(ValueError, match="unauthorized or duplicate"):
            select(store, hybrid_retriever=InvalidRanker())


def test_cache_only_miss_falls_back_to_lexical_without_api_client(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        ingest(store, candidate("literal", value="Late payouts need review."))
        ingest(store, candidate("paraphrase", value="Settlement delays occur after bank holidays."))
        with HybridRetriever(tmp_path / "empty-cache.sqlite3", allow_remote=False) as retriever:
            result = select(store, hybrid_retriever=retriever)
    assert result["status"] == "ready"
    assert result["retrieval"] == "lexical_fallback"
    assert result["retrieval_details"]["semantic_status"] == "cache_miss"
    assert [record["id"] for record in result["selected"]] == ["literal"]
