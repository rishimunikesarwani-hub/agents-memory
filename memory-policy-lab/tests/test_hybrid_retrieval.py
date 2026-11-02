"""Offline mechanics tests. Hand-authored vectors do not establish semantic quality."""
from dataclasses import replace
import json
import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai
import pytest

from src import embedding_adapter
from src.embedding_adapter import EmbeddingError, OpenAIEmbedder
from src.hybrid_retrieval import HybridConfig, HybridRetriever, record_text


PRINCIPAL = {"user_id": "synthetic-a", "role": "user"}
CONFIG = HybridConfig(provider="fixture", model="hand-authored-v1", dimensions=3)


class FixtureEmbedder:
    """Return specified test vectors. This is not an embedding model."""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [self.mapping.get(text, [1.0, 0.0, 0.0]) for text in texts]


@pytest.fixture(autouse=True)
def no_live_api(monkeypatch):
    factory = MagicMock(side_effect=AssertionError("Tests must not create a real API client."))
    monkeypatch.setattr(embedding_adapter.openai, "OpenAI", factory)
    return factory


def record(identifier, key="garage", value="vehicle maintenance", observed_at=1):
    return {"id": identifier, "key": key, "value": value, "observed_at": observed_at}


def make_retriever(tmp_path, embedder=None, *, allow_remote=True, config=CONFIG):
    return HybridRetriever(tmp_path / "embedding-cache.sqlite", config=config,
                           embedder=embedder or FixtureEmbedder(), allow_remote=allow_remote)


def test_synonym_fixture_with_zero_word_overlap_is_retrieved(tmp_path):
    candidate = record("relevant")
    distractor = record("other", "orchard", "apples")
    embedder = FixtureEmbedder({record_text(distractor): [0.0, 1.0, 0.0]})
    with make_retriever(tmp_path, embedder) as retriever:
        result = retriever.rank("automobile repair", [candidate, distractor], PRINCIPAL, "wf")
    assert result["mode"] == "hybrid"
    assert result["semantic_status"] == "ready"
    assert [row["id"] for row in result["ranked"]] == ["relevant"]
    assert result["ranked"][0]["lexical_score"] == 0
    assert result["ranked"][0]["cosine"] == pytest.approx(1)
    assert result["diagnostics"]["embedding_source"] == "injected_vectors"
    assert result["diagnostics"]["threshold_validated"] is False


def test_exact_word_candidate_survives_below_semantic_threshold(tmp_path):
    candidate = record("lexical", "refund", "approved")
    embedder = FixtureEmbedder({record_text(candidate): [0, 1, 0]})
    with make_retriever(tmp_path, embedder) as retriever:
        result = retriever.rank("refund", [candidate], PRINCIPAL, "wf")
    row = result["ranked"][0]
    assert row["id"] == "lexical"
    assert row["lexical_score"] == 1
    assert row["lexical_rank"] == 1
    assert row["semantic_rank"] is None
    assert row["cosine"] == 0


def test_rrf_rewards_evidence_from_both_rankings(tmp_path):
    both = record("both", "car", "refund")
    lexical = record("lexical", "car", "administration")
    semantic = record("semantic", "vehicle", "repayment")
    embedder = FixtureEmbedder({record_text(both): [0.9, 0.1, 0],
                               record_text(lexical): [0, 1, 0]})
    with make_retriever(tmp_path, embedder) as retriever:
        result = retriever.rank("car refund", [lexical, semantic, both], PRINCIPAL, "wf")
    assert {row["id"] for row in result["ranked"]} == {"both", "lexical", "semantic"}
    assert result["ranked"][0]["id"] == "both"
    assert result["ranked"][0]["score"] == pytest.approx(1 / 61 + 1 / 62)


def test_equal_fusion_scores_use_recency_then_id(tmp_path):
    older = record("older", "first", "second", observed_at=1)
    newer = record("newer", "first", "other", observed_at=2)
    embedder = FixtureEmbedder({record_text(older): [0.9, 0.1, 0]})
    with make_retriever(tmp_path, embedder) as retriever:
        result = retriever.rank("first second", [older, newer], PRINCIPAL, "wf")
    assert result["ranked"][0]["score"] == result["ranked"][1]["score"]
    assert [row["id"] for row in result["ranked"]] == ["newer", "older"]


def test_semantic_candidates_are_limited_to_twenty(tmp_path):
    records = [record(f"r{index:02}", value=str(index), observed_at=index) for index in range(25)]
    with make_retriever(tmp_path) as retriever:
        result = retriever.rank("unmatched", records, PRINCIPAL, "wf")
    assert len(result["ranked"]) == 20
    assert [row["id"] for row in result["ranked"]] == [f"r{index:02}" for index in range(24, 4, -1)]


@pytest.mark.parametrize("bad", [[1, 0], [float("nan"), 1, 0], [float("inf"), 1, 0],
                                  [0, 0, 0], [True, 0, 1], [10**1000, 1, 0]])
def test_invalid_vectors_never_enter_cache(tmp_path, bad):
    candidate = record("bad")
    with make_retriever(tmp_path, FixtureEmbedder({record_text(candidate): bad})) as retriever:
        with pytest.raises(EmbeddingError):
            retriever.rank("automobile repair", [candidate], PRINCIPAL, "wf")
        assert retriever.connection.execute("SELECT count(*) FROM embedding_vectors").fetchone()[0] == 0


@pytest.mark.parametrize("field", ["key", "value"])
def test_full_record_content_hash_prevents_stale_vector_reuse(tmp_path, field):
    candidate = record("r1")
    embedder = FixtureEmbedder()
    with make_retriever(tmp_path, embedder) as retriever:
        retriever.rank("automobile repair", [candidate], PRINCIPAL, "wf")
        changed = {**candidate, field: candidate[field] + " revised"}
        retriever.allow_remote = False
        result = retriever.rank("automobile repair", [changed], PRINCIPAL, "wf")
        assert result["mode"] == "lexical_fallback"
        assert result["diagnostics"]["cache_hits"] == 1
        assert result["diagnostics"]["cache_misses"] == 1
        assert len(embedder.calls) == 1
        retriever.allow_remote = True
        retriever.rank("automobile repair", [changed], PRINCIPAL, "wf")
    assert embedder.calls[-1] == [record_text(changed)]


@pytest.mark.parametrize("principal,workflow", [({"user_id": "synthetic-b"}, "wf"),
                                                 (PRINCIPAL, "different"),
                                                 ({"user_id": "synthetic-a", "role": "admin"}, "wf")])
def test_cache_namespace_separates_principals_roles_and_workflows(tmp_path, principal, workflow):
    embedder = FixtureEmbedder()
    with make_retriever(tmp_path, embedder) as retriever:
        retriever.rank("automobile repair", [record("r1")], PRINCIPAL, "wf")
        retriever.allow_remote = False
        result = retriever.rank("automobile repair", [record("r1")], principal, workflow)
    assert result["semantic_status"] == "cache_miss"
    assert result["diagnostics"]["cache_hits"] == 0
    assert len(embedder.calls) == 1


@pytest.mark.parametrize("config", [replace(CONFIG, provider="different"),
                                     replace(CONFIG, model="hand-authored-v2"), replace(CONFIG, dimensions=2)])
def test_cache_separates_provider_model_and_dimensions(tmp_path, config):
    with make_retriever(tmp_path) as retriever:
        retriever.rank("query", [record("r1")], PRINCIPAL, "wf")
    with make_retriever(tmp_path, config=config, allow_remote=False) as retriever:
        result = retriever.rank("query", [record("r1")], PRINCIPAL, "wf")
    assert result["semantic_status"] == "cache_miss"
    assert result["diagnostics"]["cache_hits"] == 0


def test_vectors_persist_and_cache_only_complete_request_uses_no_embedder(tmp_path, no_live_api):
    candidate = record("r1")
    with make_retriever(tmp_path) as retriever:
        retriever.rank("automobile repair", [candidate], PRINCIPAL, "wf")
    forbidden = MagicMock()
    forbidden.embed.side_effect = AssertionError("Cache-only mode must not call embedder.")
    with make_retriever(tmp_path, forbidden, allow_remote=False) as retriever:
        result = retriever.rank("automobile repair", [candidate], PRINCIPAL, "wf")
    assert result["mode"] == "hybrid"
    assert result["diagnostics"]["cache_hits"] == 2
    assert result["diagnostics"]["embedding_batches"] == 0
    forbidden.embed.assert_not_called()
    no_live_api.assert_not_called()


def test_missing_cache_explicitly_falls_back_without_remote_calls(tmp_path, no_live_api):
    with HybridRetriever(tmp_path / "cache.sqlite", allow_remote=False) as retriever:
        result = retriever.rank("refund", [record("r1", "refund", "approved")], PRINCIPAL, "wf")
    assert result["mode"] == "lexical_fallback"
    assert result["semantic_status"] == "cache_miss"
    assert result["ranked"][0]["lexical_score"] == 1
    assert result["ranked"][0]["cosine"] is None
    no_live_api.assert_not_called()


def test_query_cache_miss_requires_complete_cache_for_hybrid(tmp_path):
    embedder = FixtureEmbedder()
    with make_retriever(tmp_path, embedder) as retriever:
        retriever.rank("query one", [record("r1")], PRINCIPAL, "wf")
        retriever.allow_remote = False
        result = retriever.rank("query two", [record("r1")], PRINCIPAL, "wf")
    assert result["semantic_status"] == "cache_miss"
    assert result["diagnostics"]["cache_hits"] == 1
    assert result["diagnostics"]["cache_misses"] == 1
    assert len(embedder.calls) == 1


def test_missing_vectors_are_batched_at_128(tmp_path):
    embedder = FixtureEmbedder()
    records = [record(str(index), value=f"value {index}") for index in range(260)]
    with make_retriever(tmp_path, embedder) as retriever:
        result = retriever.rank("query", records, PRINCIPAL, "wf")
    assert [len(batch) for batch in embedder.calls] == [128, 128, 5]
    assert result["diagnostics"]["embedded_items"] == 261
    assert result["diagnostics"]["embedding_batches"] == 3


def test_embedder_error_is_visible_and_safe(tmp_path):
    embedder = MagicMock()
    embedder.embed.side_effect = RuntimeError("RAW_PROVIDER_BODY_SECRET")
    with make_retriever(tmp_path, embedder) as retriever:
        with pytest.raises(EmbeddingError, match="Embedding retrieval failed") as raised:
            retriever.rank("query", [record("r1")], PRINCIPAL, "wf")
        assert retriever.connection.execute("SELECT count(*) FROM embedding_vectors").fetchone()[0] == 0
    assert "RAW_PROVIDER_BODY_SECRET" not in str(raised.value)


def sdk_response(*, indices=(1, 0), model="text-embedding-3-small", vectors=None):
    vectors = vectors or [[1, 0, 0], [0, 1, 0]]
    return SimpleNamespace(model=model, data=[SimpleNamespace(index=index, embedding=vectors[index % 2]) for index in indices])


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-noncredential")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid/v1")
    client = MagicMock()
    client.embeddings.create.return_value = sdk_response()
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(embedding_adapter.openai, "OpenAI", factory)
    return factory, client


def test_openai_batch_indices_restore_input_order_and_explicit_config(sdk):
    vectors = OpenAIEmbedder(dimensions=3).embed(["first", "second"])
    assert vectors == [[1, 0, 0], [0, 1, 0]]
    sdk[1].embeddings.create.assert_called_once_with(
        model="text-embedding-3-small", dimensions=3, encoding_format="float", input=["first", "second"])
    assert sdk[0].call_args.kwargs["base_url"] == "https://api.openai.com/v1"
    assert sdk[0].call_args.kwargs["max_retries"] == 0
    sdk[1].close.assert_called_once()


@pytest.mark.parametrize("indices", [(0, 0), (0,), (0, 2), (-1, 0), (True, 0)])
def test_invalid_batch_indices_fail_visibly(sdk, indices):
    sdk[1].embeddings.create.return_value = sdk_response(indices=indices)
    with pytest.raises(EmbeddingError):
        OpenAIEmbedder(dimensions=3).embed(["first", "second"])


def test_response_model_must_match_requested_model(sdk):
    sdk[1].embeddings.create.return_value = sdk_response(model="different-model")
    with pytest.raises(EmbeddingError, match="response model differs"):
        OpenAIEmbedder(dimensions=3).embed(["first", "second"])


def test_openai_failure_exposes_no_raw_body_or_key(sdk):
    raw = "RAW_PROVIDER_BODY_SECRET test-only-noncredential"
    sdk[1].embeddings.create.side_effect = openai.BadRequestError(
        raw, response=httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com/v1/embeddings")),
        body={"detail": raw})
    with pytest.raises(EmbeddingError, match="OpenAI embedding request failed") as raised:
        OpenAIEmbedder(dimensions=3).embed(["first"])
    assert raw not in str(raised.value)


def test_missing_embedding_key_is_actionable_and_does_not_create_client(sdk, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY is missing"):
        OpenAIEmbedder(dimensions=3).embed(["first"])
    sdk[0].assert_not_called()


def test_default_embedding_configuration_and_immutable_config():
    config = HybridConfig()
    assert config.provider == "openai"
    assert config.model == "text-embedding-3-small"
    assert config.dimensions == 512
    assert config.cosine_threshold == 0.35
    with pytest.raises(AttributeError):
        config.model = "changed"
