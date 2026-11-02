import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.storage import checkpoint_serializer


def child(ctx, action, *, thread="restart", memory=False, key=""):
    command = [
        sys.executable,
        str(Path(__file__).with_name("restart_process.py")),
        action,
        "--org",
        ctx.org_id,
        "--user",
        ctx.user_id,
        "--thread",
        thread,
    ]
    if memory:
        command.append("--memory")
    # An empty key overrides any optional real encryption key in the local .env.
    environment = {**os.environ, "LANGGRAPH_AES_KEY": key}
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=45, check=False)
    data = json.loads(result.stdout.strip().splitlines()[-1])
    receipt = {
        "action": action,
        "backend": "memory" if memory else "postgres",
        "org": ctx.org_id,
        "user": ctx.user_id,
        "thread": thread,
        "encrypted": bool(key),
        "exit_code": result.returncode,
        "actual": data,
    }
    receipt_path = Path(__file__).resolve().parents[1] / "runs" / f"demo2-process-{os.getpid()}.jsonl"
    with receipt_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt) + "\n")
    return result.returncode, data


@pytest.fixture
def restart_proof(ctx, request, postgres_backends):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Database restart proof runs in the PostgreSQL verification layer.")
    first_code, first = child(ctx, "seed")
    assert first_code == 0, first
    # subprocess.run returns only after Process A exits.
    second_code, second = child(ctx, "read")
    assert second_code == 0, second
    return first, second


def test_d2_01_original_process_exits_before_restore(restart_proof):
    first, second = restart_proof
    assert first["pid"] != second["pid"]


def test_d2_02_parent_messages_restore_exactly(restart_proof):
    first, second = restart_proof
    assert first["messages"] == second["messages"]
    assert any(m["id"] == "m1" for m in second["messages"])


def test_d2_03_long_term_records_restore(restart_proof):
    first, second = restart_proof
    assert first["facts"] == second["facts"]
    assert first["episodes"] == second["episodes"]
    assert first["procedural"] == second["procedural"]
    assert second["procedural"]["workflow"] == "Check the invoice."


def test_d2_04_vector_search_after_restart(restart_proof):
    first, second = restart_proof
    assert {f["key"] for f in first["semantic"]} == {f["key"] for f in second["semantic"]}
    assert second["semantic"][0]["fact"] == "User prefers dark mode."


def test_d2_05_new_message_appends_once(ctx, restart_proof):
    code, continued = child(ctx, "continue")
    assert code == 0, continued
    humans = [m for m in continued["messages"] if m["role"] == "human"]
    assert [m["id"] for m in humans] == ["m1", "m2"]
    code, repeated = child(ctx, "continue")
    assert code == 0
    assert repeated["messages"] == continued["messages"]


def test_d2_06_new_thread_has_only_long_term_memory(ctx, restart_proof):
    code, fresh = child(ctx, "read", thread="different")
    assert code == 0
    assert fresh["messages"] == []
    assert fresh["facts"] == restart_proof[0]["facts"]


def test_d2_07_in_memory_negative_control(ctx):
    first_code, first = child(ctx, "seed", memory=True)
    second_code, second = child(ctx, "read", memory=True)
    assert first_code == second_code == 0
    assert first["messages"] and first["facts"]
    assert second["messages"] == [] and second["facts"] == []
    assert second["episodes"] == []


def test_d2_08_database_save_failure_is_not_success(ctx, postgres_backends, request, provider):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Database failure proof runs in the PostgreSQL verification layer.")
    from conftest import fixture_embeddings
    from user_memory.service import UserMemoryService
    from user_memory.storage import open_postgres

    def embed(texts):
        return [v + [0.0] * (1536 - len(v)) for v in fixture_embeddings(texts)]

    with open_postgres(
        os.environ["TEST_DATABASE_URL"], embed_texts=embed, dims=1536, test_database=True
    ) as backends:
        service = UserMemoryService(backends.store)
        original = provider.propose

        def close_connection_before_save(*args):
            update = original(*args)
            backends.store.conn.close()
            return update

        provider.propose = close_connection_before_save
        app = MemoryApplication(
            service, provider, backends.checkpointer, Settings(sync_strategy="every_turn")
        )
        result = app.send(ctx, "failure", "I use dark mode and prefer US English.", "m1")
        assert result["trace"]["memory_update"] == "failed"
        assert result.get("last_sync_human_count", 0) == 0
    assert postgres_backends.store.get(ctx.namespace("profile"), "document") is None


def test_d2_09_encrypted_restart_correct_and_wrong_keys(ctx, request, postgres_backends):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Encrypted database restore runs in the PostgreSQL verification layer.")
    key = "11" * 32
    assert child(ctx, "seed", key=key)[0] == 0
    assert child(ctx, "read", key=key)[0] == 0
    wrong_code, wrong = child(ctx, "read", key="22" * 32)
    assert wrong_code != 0 and wrong["error_type"] == "ValueError"
    from user_memory.service import UserMemoryService

    app = MemoryApplication(
        UserMemoryService(postgres_backends.store), None, postgres_backends.checkpointer, Settings()
    )
    thread_id = app.config(ctx, "restart")["configurable"]["thread_id"]
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], connect_timeout=5) as conn:
        rows = conn.execute(
            "SELECT type, blob FROM checkpoint_blobs WHERE thread_id=%s", (thread_id,)
        ).fetchall()
    assert any("+aes" in row[0] for row in rows)
    assert all(b"I use dark mode" not in bytes(row[1]) for row in rows if row[1] is not None)


def test_d2_09_hex_key_validation():
    assert checkpoint_serializer("") is None
    with pytest.raises(ValueError, match="64 hexadecimal"):
        checkpoint_serializer("not-a-key")
