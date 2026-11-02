import copy
import math
import os
import re
import uuid

import psycopg
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from user_memory.models import AppContext, AssistantReply, FactProposal, MemoryUpdate
from user_memory.service import UserMemoryService
from user_memory.storage import open_postgres


@pytest.fixture(scope="session")
def postgres_backends(request):
    if request.config.getoption("--backend") != "postgres":
        yield None
        return
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url or "YOUR_LOCAL_PASSWORD" in url:
        pytest.skip("BLOCKED: TEST_DATABASE_URL is unavailable; PostgreSQL acceptance remains incomplete.")
    try:
        with psycopg.connect(url, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        pytest.skip("BLOCKED: the dedicated PostgreSQL test database is unavailable.")

    def embed(texts):
        return [v + [0.0] * (1536 - len(v)) for v in fixture_embeddings(texts)]

    with open_postgres(url, embed_texts=embed, dims=1536, setup=True, test_database=True) as backends:
        yield backends


def fixture_embeddings(texts):
    """Controlled semantic vectors. These are not OpenAI embedding evidence."""
    axes = ("dark light appearance theme", "english language", "billing charged refund", "fraud berlin")
    vectors = []
    for text in texts:
        words = re.findall(r"[a-z]+", text.lower())
        vector = [float(sum(word in axis.split() for word in words)) for axis in axes]
        if not any(vector):
            vector[-1] = 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1
        vectors.append([x / norm for x in vector])
    return vectors


class FixtureProvider:
    """Explicit fixtures for state and storage tests. No live inference occurs."""

    def __init__(self):
        self.prompts = []
        self.updates = 0

    def reply(self, messages, context):
        self.prompts.append(context)
        return AssistantReply(reply="Fixture answer; inspect records for storage evidence.")

    def propose(self, messages, current, scope):
        self.updates += 1
        return MemoryUpdate(
            new_facts=[
                FactProposal(content="User prefers dark mode.", category="preference", confidence=0.95),
                FactProposal(content="User prefers US English.", category="preference", confidence=0.95),
            ]
        )


@pytest.fixture
def ctx():
    return AppContext(org_id="test-org-" + uuid.uuid4().hex, user_id=uuid.uuid4().hex)


@pytest.fixture
def store(postgres_backends):
    if postgres_backends is not None:
        return postgres_backends.store
    return InMemoryStore(index={"dims": 4, "embed": fixture_embeddings, "fields": ["mem_ix"]})


@pytest.fixture
def service(store):
    return UserMemoryService(store)


@pytest.fixture
def provider():
    return FixtureProvider()


@pytest.fixture
def checkpointer(postgres_backends):
    if postgres_backends is not None:
        return postgres_backends.checkpointer
    return InMemorySaver()


@pytest.fixture(autouse=True)
def record_memory_evidence(request, monkeypatch):
    """Attach scoped observations to pytest JSON, without inspecting clients or credentials."""
    from user_memory.app import MemoryApplication

    original = MemoryApplication.send

    def observed_send(app, context, thread_id, text, message_id):
        result = original(app, context, thread_id, text, message_id)
        event = {
            "org": context.org_id,
            "user": context.user_id,
            "thread": thread_id,
            "input_message_id": message_id,
            "input_text": text,
            "actual_trace": copy.deepcopy(result.get("trace", {})),
            "human_count": result.get("human_count", 0),
            "last_successful_sync": result.get("last_sync_human_count", 0),
            "message_ids": [m.id for m in result["messages"]],
        }
        try:
            snapshot = app.graph.get_state(app.config(context, thread_id))
            event["checkpoint_id"] = snapshot.config["configurable"].get("checkpoint_id")
            event["facts"] = app.service.profile(context)["facts"]
        except Exception as exc:  # noqa: BLE001 - unavailable inspection is recorded without raw errors
            event["inspection_error_type"] = type(exc).__name__
        request.node.user_properties.append(("memory_observation", event))
        return result

    monkeypatch.setattr(MemoryApplication, "send", observed_send)
    yield
    service = request.node.funcargs.get("service")
    context = request.node.funcargs.get("ctx")
    if service is not None and context is not None:
        try:
            request.node.user_properties.append(
                (
                    "stored_profile",
                    {
                        "org": context.org_id,
                        "user": context.user_id,
                        "actual": service.profile(context),
                        "organization": service.profile(context, shared=True),
                        "semantic_keys": [row.key for row in service.list_semantic(context)],
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001 - retain the failure class without connection secrets
            request.node.user_properties.append(("inspection_error_type", type(exc).__name__))
