import os
import re
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo


@dataclass
class Backends:
    checkpointer: PostgresSaver
    store: PostgresStore


class StorageConfigurationError(ValueError):
    """Safe configuration messages that do not contain connection credentials."""


def checkpoint_serializer(key_hex: str | None = None):
    value = os.getenv("LANGGRAPH_AES_KEY", "") if key_hex is None else key_hex
    if not value.strip():
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value.strip()):
        raise ValueError("LANGGRAPH_AES_KEY must contain 64 hexadecimal characters.")
    return EncryptedSerializer.from_pycryptodome_aes(key=bytes.fromhex(value.strip()))


@contextmanager
def open_postgres(
    database_url: str, *, embed_texts, dims: int, setup: bool = False, test_database: bool = False, serde=None
):
    """Keep both connection context managers alive for the application lifetime."""
    if not database_url:
        raise ValueError("Set DATABASE_URL for PostgreSQL with pgvector.")
    info = conninfo_to_dict(database_url)
    if test_database and not info.get("dbname", "").endswith("_test"):
        raise ValueError("Integration tests require a dedicated database with a name ending in _test.")
    if dims < 1:
        raise ValueError("Embedding dimensions must be positive.")
    database_url = make_conninfo(database_url, connect_timeout=5)
    with ExitStack() as stack:
        checkpointer = stack.enter_context(PostgresSaver.from_conn_string(database_url))
        if serde is not None:
            checkpointer = PostgresSaver(checkpointer.conn, serde=serde)
        store = stack.enter_context(
            PostgresStore.from_conn_string(
                database_url,
                index={"embed": embed_texts, "dims": dims, "fields": ["mem_ix"]},
            )
        )
        if setup:
            checkpointer.setup()
            store.setup()
        row = store.conn.execute(
            "SELECT a.atttypmod AS dims FROM pg_attribute a "
            "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.relname='store_vectors' AND a.attname='embedding' AND n.nspname=current_schema()"
        ).fetchone()
        if row is None:
            raise StorageConfigurationError("Database schema is missing. Run user-memory db-init.")
        if row["dims"] != dims:
            raise StorageConfigurationError(
                f"Database vector index has {row['dims']} dimensions; configured value is {dims}."
            )
        yield Backends(checkpointer=checkpointer, store=store)
