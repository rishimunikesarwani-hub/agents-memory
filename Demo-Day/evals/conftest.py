import os

import pytest

from user_memory.config import Settings
from user_memory.provider import OpenAIProvider


@pytest.fixture
def live_provider():
    if os.getenv("RUN_LIVE_OPENAI") != "1" or not os.getenv("OPENAI_API_KEY", "").strip():
        pytest.skip("BLOCKED: live OpenAI checks require a local key and RUN_LIVE_OPENAI=1.")
    return OpenAIProvider(Settings.from_env())
