import os
import uuid

import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from conftest import FixtureProvider, fixture_embeddings
from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import AppContext
from user_memory.service import UserMemoryService
from user_memory.storage import open_postgres

pytestmark = pytest.mark.postgres


def test_d1_03_checkpoint_committed_outside_app_connection():
    database_url = os.getenv("TEST_DATABASE_URL", "")
    if not database_url or "YOUR_LOCAL_PASSWORD" in database_url:
        pytest.skip("BLOCKED: configure TEST_DATABASE_URL for the dedicated memory_test database.")
    try:
        with psycopg.connect(database_url, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        pytest.skip("BLOCKED: start the dedicated PostgreSQL test database in Docker.")
    ctx = AppContext(org_id="integration", user_id=uuid.uuid4().hex)

    def padded_embeddings(texts):
        return [v + [0.0] * (1536 - len(v)) for v in fixture_embeddings(texts)]

    with open_postgres(
        database_url, embed_texts=padded_embeddings, dims=1536, setup=True, test_database=True
    ) as backends:
        app = MemoryApplication(
            UserMemoryService(backends.store),
            FixtureProvider(),
            backends.checkpointer,
            Settings(sync_strategy="every_turn"),
        )
        out = app.send(ctx, "preference", "I use dark mode and prefer US English.", "m1")
        assert out["trace"]["memory_update"] == "saved"
        config = app.config(ctx, "preference")
        with PostgresSaver.from_conn_string(database_url) as independent:
            checkpoint = independent.get_tuple(config)
            messages = checkpoint.checkpoint["channel_values"]["messages"]
            assert any(m.id == "m1" and "dark mode" in m.content for m in messages)
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT count(*) FROM checkpoints WHERE thread_id = %s",
                (config["configurable"]["thread_id"],),
            ).fetchone()
            assert row[0] >= 1


def test_database_guard_does_not_target_non_test_database():
    with (
        pytest.raises(ValueError, match="_test"),
        open_postgres(
            "postgresql://localhost/real_customer_data",
            embed_texts=fixture_embeddings,
            dims=4,
            test_database=True,
        ),
    ):
        pass


def test_oa_06_database_vector_dimension_drift(postgres_backends, request):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Physical vector dimensions are checked in the PostgreSQL verification layer.")
    with (
        pytest.raises(ValueError, match="1536.*768"),
        open_postgres(
            os.environ["TEST_DATABASE_URL"],
            embed_texts=lambda texts: [[1.0] * 768 for _ in texts],
            dims=768,
            test_database=True,
        ),
    ):
        pass
