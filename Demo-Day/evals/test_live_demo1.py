"""Billed provider checks. A skipped check is incomplete acceptance, not a pass."""

import uuid

import pytest
from langchain_core.messages import HumanMessage
from langgraph.store.memory import InMemoryStore

from user_memory.models import AppContext, AssistantReply, MemoryUpdate
from user_memory.service import UserMemoryService

pytestmark = pytest.mark.live


def test_oa_05_live_embedding_dimensions(live_provider):
    result = live_provider.embed_texts(["User prefers dark mode."])
    assert len(result) == 1
    assert len(result[0]) == 1536


def test_oa_04_and_d1_live_extraction_and_recall(live_provider):
    message = HumanMessage(content="I use dark mode and prefer US English.", id="live-m1")
    store = InMemoryStore(index={"dims": 1536, "embed": live_provider.embed_texts, "fields": ["mem_ix"]})
    service = UserMemoryService(store)
    ctx = AppContext(org_id="live-test", user_id=uuid.uuid4().hex)
    update = live_provider.propose([message], service.profile(ctx), "user")
    assert isinstance(update, MemoryUpdate)
    memory = service.apply_update(ctx, update, thread_id="live", message_id="live-m1")
    content = " ".join(f["content"] for f in memory["facts"]).lower()
    assert "dark" in content and "english" in content
    context, ids = service.context(ctx, "What appearance and language do I prefer?")
    assert ids
    reply = live_provider.reply([HumanMessage(content="What appearance and language do I prefer?")], context)
    assert isinstance(reply, AssistantReply)
    assert "dark" in reply.reply.lower() and "english" in reply.reply.lower()
