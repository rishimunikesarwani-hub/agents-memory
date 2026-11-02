"""Fuse lexical and cosine rankings over records already approved by memory policy."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3

if __package__:
    from .embedding_adapter import EmbeddingError, OpenAIEmbedder, validate_vector
else:
    from embedding_adapter import EmbeddingError, OpenAIEmbedder, validate_vector


@dataclass(frozen=True)
class HybridConfig:
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 512
    cosine_threshold: float = 0.35
    semantic_top_k: int = 20
    rrf_k: int = 60
    batch_size: int = 128

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip() for value in (self.provider, self.model)):
            raise ValueError("Embedding provider and model must be nonempty strings.")
        if type(self.dimensions) is not int or self.dimensions < 1:
            raise ValueError("Embedding dimensions must be a positive integer.")
        if (type(self.cosine_threshold) not in (int, float)
                or not math.isfinite(self.cosine_threshold) or not -1 <= self.cosine_threshold <= 1):
            raise ValueError("Cosine threshold must be finite and between -1 and 1.")
        for value, maximum, name in ((self.semantic_top_k, 20, "semantic_top_k"),
                                     (self.batch_size, 128, "batch_size")):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer between 1 and {maximum}.")
        if type(self.rrf_k) is not int or self.rrf_k < 1:
            raise ValueError("rrf_k must be a positive integer.")


def record_text(record):
    """Serialize the complete key and value without shortening or adding other records."""
    return json.dumps({"key": record["key"], "value": record["value"]},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine(left, right):
    left_norm, right_norm = math.hypot(*left), math.hypot(*right)
    similarity = math.fsum((x / left_norm) * (y / right_norm) for x, y in zip(left, right))
    return max(-1.0, min(1.0, similarity))


class HybridRetriever:
    """Keep cached vectors separate by model, principal, workflow, and full text hash.

    The caller must filter authorization, validity, and expiry before rank().
    SQLite stores vectors. Python calculates cosine similarity without a vector index.
    """

    def __init__(self, cache_path=None, *, config=None, embedder=None, allow_remote=False):
        self.config = config or HybridConfig()
        if type(allow_remote) is not bool:
            raise ValueError("allow_remote must be a boolean.")
        if embedder is None and self.config.provider != "openai":
            raise ValueError("A custom embedding provider requires an injected embedder.")
        self.allow_remote = allow_remote
        self.injected_embedder = embedder is not None
        self.embedder = embedder or OpenAIEmbedder(model=self.config.model, dimensions=self.config.dimensions)
        self.cache_path = Path(cache_path) if cache_path is not None else Path(__file__).resolve().parents[1] / "data" / "embedding-cache.sqlite"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.cache_path, timeout=15)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS embedding_vectors (
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                namespace TEXT NOT NULL,
                kind TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                vector TEXT NOT NULL,
                PRIMARY KEY(provider, model, dimensions, namespace, kind, text_hash)
            )
        """)
        self.connection.commit()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def _namespace(self, principal, workflow):
        if (not isinstance(principal, dict) or not isinstance(principal.get("user_id"), str)
                or not principal["user_id"] or principal.get("role", "user") not in {"user", "admin"}
                or not isinstance(workflow, str) or not workflow):
            raise ValueError("Retrieval requires a runtime principal and workflow namespace.")
        return _digest(json.dumps({"user_id": principal["user_id"], "role": principal.get("role", "user"),
                                   "workflow": workflow}, sort_keys=True, separators=(",", ":")))

    def _cache_key(self, namespace, kind, text_hash):
        return (self.config.provider, self.config.model, self.config.dimensions, namespace, kind, text_hash)

    def _read_vector(self, namespace, kind, text_hash):
        row = self.connection.execute(
            "SELECT vector FROM embedding_vectors WHERE provider=? AND model=? AND dimensions=? AND namespace=? AND kind=? AND text_hash=?",
            self._cache_key(namespace, kind, text_hash),
        ).fetchone()
        if row is None:
            return None
        try:
            return validate_vector(json.loads(row[0]), self.config.dimensions)
        except (ValueError, TypeError):
            raise EmbeddingError("Cached embedding contains invalid vector data.") from None

    def rank(self, query, records, principal, workflow):
        """Return fused candidates or an explicit lexical fallback when cache data is absent."""
        if __package__:
            from .memory_policy import _terms
        else:
            from memory_policy import _terms
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Retrieval query must be a nonempty string.")
        namespace = self._namespace(principal, workflow)
        records = list(records)
        by_id = {record["id"]: record for record in records}
        if len(by_id) != len(records):
            raise ValueError("Retrieval record IDs must be unique.")
        query_terms = _terms(query)
        lexical = {record["id"]: len(query_terms & _terms(record["value"] + " " + record["key"])) for record in records}
        lexical_order = sorted((identifier for identifier, score in lexical.items() if score > 0),
                               key=lambda identifier: (-lexical[identifier], -by_id[identifier]["observed_at"], identifier))
        lexical_ranks = {identifier: index for index, identifier in enumerate(lexical_order, 1)}
        diagnostics = {
            "eligible_records": len(records), "cache_hits": 0, "cache_misses": 0,
            "embedded_items": 0, "embedding_batches": 0, "dimensions": self.config.dimensions,
            "cosine_threshold": self.config.cosine_threshold, "threshold_validated": False,
            "semantic_top_k": self.config.semantic_top_k, "rrf_k": self.config.rrf_k,
            "embedding_source": "injected_vectors" if self.injected_embedder else "openai_vectors",
            "cache_namespace": namespace,
        }

        def result(cosines=None, semantic_ranks=None, *, semantic_status="ready"):
            semantic_ranks = semantic_ranks or {}
            identifiers = set(lexical_ranks) | set(semantic_ranks)
            ranked = []
            for identifier in identifiers:
                lexical_rank, semantic_rank = lexical_ranks.get(identifier), semantic_ranks.get(identifier)
                score = sum(1 / (self.config.rrf_k + rank) for rank in (lexical_rank, semantic_rank) if rank is not None)
                ranked.append({"id": identifier, "score": score, "lexical_score": lexical[identifier],
                               "cosine": cosines.get(identifier) if cosines is not None else None,
                               "lexical_rank": lexical_rank, "semantic_rank": semantic_rank})
            ranked.sort(key=lambda row: (-row["score"], -by_id[row["id"]]["observed_at"], row["id"]))
            return {"ranked": ranked, "mode": "hybrid" if cosines is not None else "lexical_fallback",
                    "semantic_status": semantic_status, "provider": self.config.provider,
                    "model": self.config.model, "diagnostics": diagnostics}

        if not records:
            return result(semantic_status="no_records")
        query_key = ("query", _digest(query))
        entries = {query_key: query}
        record_keys = {}
        for record in records:
            text = record_text(record)
            cache_key = ("record", _digest(text))
            record_keys[record["id"]] = cache_key
            entries[cache_key] = text
        vectors, missing = {}, []
        for key, text in entries.items():
            vector = self._read_vector(namespace, *key)
            if vector is None:
                missing.append((key, text))
            else:
                vectors[key] = vector
        diagnostics.update(cache_hits=len(vectors), cache_misses=len(missing))
        if missing and not self.allow_remote:
            return result(semantic_status="cache_miss")
        for offset in range(0, len(missing), self.config.batch_size):
            batch = missing[offset:offset + self.config.batch_size]
            try:
                supplied = self.embedder.embed([text for _, text in batch])
            except EmbeddingError:
                raise
            except Exception:
                raise EmbeddingError("Embedding retrieval failed. Check embedding configuration and provider access.") from None
            if not isinstance(supplied, (list, tuple)) or len(supplied) != len(batch):
                raise EmbeddingError("Embedder did not return one vector per input.")
            validated = [validate_vector(vector, self.config.dimensions) for vector in supplied]
            with self.connection:
                for (key, _), vector in zip(batch, validated):
                    self.connection.execute(
                        "INSERT OR REPLACE INTO embedding_vectors VALUES(?,?,?,?,?,?,?)",
                        (*self._cache_key(namespace, *key), json.dumps(vector, allow_nan=False, separators=(",", ":"))),
                    )
                    vectors[key] = vector
            diagnostics["embedded_items"] += len(batch)
            diagnostics["embedding_batches"] += 1
        cosines = {identifier: _cosine(vectors[query_key], vectors[key]) for identifier, key in record_keys.items()}
        semantic_order = sorted((identifier for identifier, cosine in cosines.items() if cosine >= self.config.cosine_threshold),
                                key=lambda identifier: (-cosines[identifier], -by_id[identifier]["observed_at"], identifier))[:self.config.semantic_top_k]
        semantic_ranks = {identifier: index for index, identifier in enumerate(semantic_order, 1)}
        return result(cosines, semantic_ranks)
