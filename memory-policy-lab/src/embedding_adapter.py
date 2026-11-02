"""OpenAI embedding requests with explicit dimensions and validated responses."""
from __future__ import annotations

import math

import openai

if __package__:
    from .model_adapter import BASE_URL, require_api_key
else:
    from model_adapter import BASE_URL, require_api_key


class EmbeddingError(RuntimeError):
    """A safe embedding failure that callers must report instead of hiding."""


def validate_vector(vector, dimensions):
    """Return finite, nonzero numeric coordinates with the required dimension."""
    if not isinstance(vector, (list, tuple)) or len(vector) != dimensions:
        raise EmbeddingError("Embedding vector has an unexpected dimension.")
    if any(type(value) not in (int, float) for value in vector):
        raise EmbeddingError("Embedding vector contains invalid or nonfinite coordinates.")
    try:
        values = [float(value) for value in vector]
    except (OverflowError, ValueError):
        raise EmbeddingError("Embedding vector contains invalid or nonfinite coordinates.") from None
    if not all(math.isfinite(value) for value in values):
        raise EmbeddingError("Embedding vector contains invalid or nonfinite coordinates.")
    magnitude = math.hypot(*values)
    if not math.isfinite(magnitude) or magnitude == 0:
        raise EmbeddingError("Embedding vector must have a finite nonzero magnitude.")
    return values


class OpenAIEmbedder:
    """Create embeddings only when embed() is explicitly called."""

    def __init__(self, *, model="text-embedding-3-small", dimensions=512):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Embedding model must be a nonempty string.")
        if type(dimensions) is not int or dimensions < 1:
            raise ValueError("Embedding dimensions must be a positive integer.")
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts):
        """Validate the returned model, index mapping, and complete vector batch."""
        if (not isinstance(texts, (list, tuple)) or not 1 <= len(texts) <= 128
                or any(not isinstance(text, str) or not text.strip() for text in texts)):
            raise ValueError("Embedding batches require 1 to 128 nonempty text strings.")
        try:
            key = require_api_key()
        except RuntimeError:
            raise EmbeddingError(
                "OPENAI_API_KEY is missing. Set it in this process environment before requesting embeddings."
            ) from None
        client = None
        try:
            client = openai.OpenAI(api_key=key, base_url=BASE_URL, timeout=120, max_retries=0)
            response = client.embeddings.create(
                model=self.model, dimensions=self.dimensions, encoding_format="float", input=list(texts),
            )
            if response.model != self.model:
                raise EmbeddingError("Embedding response model differs from the requested model.")
            if len(response.data) != len(texts):
                raise EmbeddingError("Embedding response does not contain every requested vector.")
            vectors = [None] * len(texts)
            for item in response.data:
                index = item.index
                if type(index) is not int or not 0 <= index < len(texts) or vectors[index] is not None:
                    raise EmbeddingError("Embedding response contains invalid or duplicate indices.")
                vectors[index] = validate_vector(item.embedding, self.dimensions)
            return vectors
        except EmbeddingError:
            raise
        except Exception:
            raise EmbeddingError(
                "OpenAI embedding request failed. Verify credentials, model access, input limits, and account quota."
            ) from None
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
