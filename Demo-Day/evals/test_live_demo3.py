import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import AppContext
from user_memory.service import UserMemoryService

pytestmark = pytest.mark.live


def test_d3_live_correction_summary_and_recall(live_provider):
    supplied_contexts = []
    original_reply = live_provider.reply

    def record_reply(messages, context):
        supplied_contexts.append({"message_ids": [m.id for m in messages], "context": context})
        return original_reply(messages, context)

    live_provider.reply = record_reply
    store = InMemoryStore(index={"dims": 1536, "embed": live_provider.embed_texts, "fields": ["mem_ix"]})
    service = UserMemoryService(store)
    ctx = AppContext(org_id="live-correction", user_id="alex")
    app = MemoryApplication(service, live_provider, InMemorySaver(), Settings(sync_strategy="every_turn"))
    first = app.send(ctx, "preferences", "I prefer dark mode and US English.", "m1")
    assert first["trace"]["memory_update"] == "saved"
    original_profile = service.profile(ctx)
    old_dark_ids = {f["id"] for f in service.profile(ctx)["facts"] if "dark" in f["content"].lower()}
    assert old_dark_ids
    second = app.send(
        ctx, "preferences", "Correction: use light mode instead of dark mode. Keep US English.", "m2"
    )
    assert second["trace"]["memory_update"] == "saved"
    facts = " ".join(f["content"] for f in service.profile(ctx)["facts"]).lower()
    corrected_profile = service.profile(ctx)
    assert "light" in facts and "english" in facts
    assert old_dark_ids.isdisjoint({f["id"] for f in service.profile(ctx)["facts"]})
    assert not any("prefers dark" in f["content"].lower() for f in service.profile(ctx)["facts"])
    summarized = app.summarize(ctx, "preferences")
    assert len(summarized["messages"]) == 1
    assert "light" in summarized["messages"][0].content.lower()
    answer = app.send(ctx, "new-thread", "Which appearance and language do I prefer?", "m3")
    text = answer["messages"][-1].content.lower()
    assert "light" in text and "english" in text
    (Path(__file__).resolve().parents[1] / "runs" / "live-correction-summary.json").write_text(
        json.dumps(
            {
                "provider": "OpenAI",
                "before": original_profile,
                "after": corrected_profile,
                "summary": summarized["messages"][0].content,
                "recall_answer": text,
                "supplied_contexts": supplied_contexts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_d3_10_and_oa_06_live_cli_policy_saved_and_reloaded(live_provider):
    org = "live-policy-" + uuid.uuid4().hex
    environment = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"], "LANGGRAPH_AES_KEY": ""}

    def invoke(*arguments):
        result = subprocess.run(
            [sys.executable, "-m", "user_memory", *arguments],
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    saved = invoke(
        "policy",
        "Pricing answers must include: Prices may change without notice.",
        "--org",
        org,
        "--user",
        "editor",
        "--admin",
    )
    loaded = invoke("profile", "--shared", "--org", org, "--user", "bob")
    assert loaded["facts"] == saved["facts"]
    results = invoke("search", "pricing disclaimer", "--shared", "--org", org, "--user", "bob")
    assert results[0]["projection_of"] == saved["facts"][0]["id"]
    other = invoke("profile", "--shared", "--org", "other-" + org, "--user", "bob")
    assert other["facts"] == []
