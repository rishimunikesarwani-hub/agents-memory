import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    chat_model: str = "gpt-4o-mini"
    memory_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dims: int = 1536
    sync_strategy: str = "interval"
    every_n_humans: int = 5
    min_conversation_chars: int = 20
    farewell_triggers: tuple[str, ...] = ("goodbye", "that's all for now", "talk later", "see you")
    profile_max_tokens: int = 2400

    def __post_init__(self):
        if self.sync_strategy not in {"interval", "farewell", "both", "every_turn"}:
            raise ValueError("Invalid MEMORY_LLM_SYNC_STRATEGY.")
        if self.every_n_humans < 1 or self.profile_max_tokens < 1 or self.embedding_dims < 1:
            raise ValueError("Message interval, token budget, and embedding dimensions must be positive.")
        if any("/" in model for model in (self.chat_model, self.memory_model, self.embedding_model)):
            raise ValueError("Use native OpenAI model identifiers without provider prefixes.")

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        return cls(
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            memory_model=os.getenv("OPENAI_MEMORY_MODEL", "gpt-4o-mini"),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_dims=int(os.getenv("OPENAI_EMBEDDING_DIMS", "1536")),
            sync_strategy=os.getenv("MEMORY_LLM_SYNC_STRATEGY", "interval"),
            every_n_humans=int(os.getenv("MEMORY_LLM_EVERY_N_HUMANS", "5")),
            min_conversation_chars=int(os.getenv("MEMORY_LLM_MIN_CONV_CHARS", "20")),
            farewell_triggers=tuple(
                t.strip().lower()
                for t in os.getenv(
                    "MEMORY_LLM_FAREWELL_TRIGGERS", "goodbye,that's all for now,talk later,see you"
                ).split(",")
                if t.strip()
            ),
            profile_max_tokens=int(os.getenv("MEMORY_PROFILE_MAX_TOKENS", "2400")),
        )
