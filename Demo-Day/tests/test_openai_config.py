import pytest

from user_memory.config import Settings
from user_memory.provider import OpenAIProvider


def test_oa_01_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(Settings(), api_key="")


def test_oa_02_03_official_clients():
    provider = OpenAIProvider(Settings(), api_key="synthetic-test-marker")
    assert provider.chat.openai_api_base == "https://api.openai.com/v1"
    assert provider.embeddings.openai_api_base == "https://api.openai.com/v1"
    assert provider.chat.model_name == "gpt-4o-mini"
    assert provider.embeddings.model == "text-embedding-3-small"
    assert "synthetic-test-marker" not in repr(provider)


def test_oa_06_dimension_mismatch():
    provider = OpenAIProvider(Settings(), api_key="synthetic-test-marker")
    with pytest.raises(ValueError, match="1536"):
        provider.validate_vectors([[0.1] * 3], expected_count=1)
