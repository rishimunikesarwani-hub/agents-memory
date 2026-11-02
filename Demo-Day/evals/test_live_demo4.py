import json
import os
import uuid
from pathlib import Path

import pytest

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import AppContext, FactProposal, MemoryUpdate
from user_memory.service import UserMemoryService
from user_memory.storage import open_postgres

pytestmark = pytest.mark.live


def test_d4_03_and_d4_10_live_worker_graph_with_postgres(live_provider):
    ctx = AppContext(org_id="live-worker-" + uuid.uuid4().hex, user_id="alex")
    traces = []
    settings = Settings(every_n_humans=1000)
    with open_postgres(
        os.environ["TEST_DATABASE_URL"], embed_texts=live_provider.embed_texts, dims=1536, test_database=True
    ) as backends:
        service = UserMemoryService(backends.store)
        memory = service.apply_update(
            ctx,
            MemoryUpdate(
                new_facts=[
                    FactProposal(
                        content="User prefers US English.",
                        category="preference",
                        confidence=0.95,
                    )
                ]
            ),
            thread_id="setup",
            message_id="explicit-fixture",
        )
        fact_id = memory["facts"][0]["id"]
        app = MemoryApplication(
            service, live_provider, backends.checkpointer, settings, context_mode="latest_only"
        )
        traces.append(app.send(ctx, "billing", "I was charged twice.", "m1")["trace"])
        traces.append(app.send(ctx, "billing", "I'm on the Pro plan.", "m2")["trace"])
    with open_postgres(
        os.environ["TEST_DATABASE_URL"], embed_texts=live_provider.embed_texts, dims=1536, test_database=True
    ) as backends:
        app = MemoryApplication(
            UserMemoryService(backends.store),
            live_provider,
            backends.checkpointer,
            settings,
            context_mode="latest_only",
        )
        final = app.send(ctx, "billing", "I want a refund.", "m3")
        traces.append(final["trace"])
        assert [t["pre_reply_count"] for t in traces] == [1, 3, 5]
        assert traces[-1]["known"] == {"issue": "duplicate", "tier": "pro", "action": "refund"}
        assert traces[-1]["supplied_message_ids"] == ["m3"]
        assert {"m1", "m2"}.issubset(traces[-1]["restored_message_ids"])
        assert fact_id in traces[-1]["retrieved_memory_ids"]
        assert "refund" in final["messages"][-1].content.lower()
        assert len(app.inspect_worker(ctx, "billing")["messages"]) == 6
        checkpoint_id = app.graph.get_state(app.config(ctx, "billing")).config["configurable"][
            "checkpoint_id"
        ]
    receipt = {
        "provider": "OpenAI",
        "backend": "PostgreSQL",
        "chat_model": settings.chat_model,
        "org": ctx.org_id,
        "user": ctx.user_id,
        "traces": traces,
        "answer": final["messages"][-1].content,
        "real_api_key_recorded": False,
        "parent_checkpoint_id": checkpoint_id,
    }
    (Path(__file__).resolve().parents[1] / "runs" / "live-worker-summary.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
