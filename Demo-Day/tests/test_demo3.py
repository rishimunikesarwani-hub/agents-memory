import copy
import json

import pytest

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import AppContext, AssistantReply, FactProposal, MemoryUpdate
from user_memory.service import token_count


def save(service, ctx, facts):
    return service.apply_update(ctx, MemoryUpdate(new_facts=facts), thread_id="preferences", message_id="m1")


def initial(service, ctx):
    return save(
        service,
        ctx,
        [
            FactProposal(content="User prefers dark mode.", category="preference", confidence=0.95),
            FactProposal(content="User prefers US English.", category="preference", confidence=0.95),
        ],
    )


def correction(service, ctx, old):
    dark_id = next(f["id"] for f in old["facts"] if "dark mode" in f["content"])
    return service.apply_update(
        ctx,
        MemoryUpdate(
            facts_to_remove=[dark_id],
            new_facts=[
                FactProposal(
                    content="User prefers light mode.",
                    category="preference",
                    confidence=0.95,
                    supersedes_fact_ids=[dark_id],
                )
            ],
        ),
        thread_id="preferences",
        message_id="m2",
    )


def test_d3_01_exact_correction(service, ctx):
    after = correction(service, ctx, initial(service, ctx))
    assert {f["content"] for f in after["facts"]} == {"User prefers light mode.", "User prefers US English."}


def test_d3_02_unrelated_preference_keeps_its_identity(service, ctx):
    before = initial(service, ctx)
    old_language = next(f for f in before["facts"] if "English" in f["content"])
    after = correction(service, ctx, before)
    assert next(f for f in after["facts"] if "English" in f["content"]) == old_language


def test_d3_03_search_reflects_current_knowledge(service, ctx):
    correction(service, ctx, initial(service, ctx))
    results = service.search(ctx, "appearance theme")
    assert results[0].value["fact"] == "User prefers light mode."
    assert not any("dark mode" in r.value["fact"] for r in results)


def test_d3_04_old_transcript_is_historical(service, ctx, provider, checkpointer):
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="every_turn"))
    app.send(ctx, "preferences", "I use dark mode and prefer US English.", "m1")
    correction(service, ctx, service.profile(ctx))
    assert any("dark mode" in str(m.content) for m in app.inspect(ctx, "preferences")["messages"])
    assert "dark mode" not in json.dumps(service.profile(ctx)["facts"])


def test_d3_05_repeat_correction_does_not_duplicate(service, ctx):
    before = initial(service, ctx)
    first = correction(service, ctx, before)
    second = correction(service, ctx, before)
    assert second["facts"] == first["facts"]


def test_d3_06_addition_preserves_unrelated_facts(service, ctx):
    before = initial(service, ctx)
    after = save(service, ctx, [FactProposal(content="On-call channel is fraud-ops.", confidence=0.95)])
    assert all(f in after["facts"] for f in before["facts"])


@pytest.mark.parametrize("removal_mode", ["explicit", "supersedes"])
def test_d3_06_reproposed_unchanged_facts_keep_ids(service, ctx, removal_mode):
    before = initial(service, ctx)
    repeated = [
        FactProposal(
            content=fact["content"],
            category=fact["category"],
            confidence=fact["confidence"],
            supersedes_fact_ids=[fact["id"]] if removal_mode == "supersedes" else [],
        )
        for fact in before["facts"]
    ]
    after = service.apply_update(
        ctx,
        MemoryUpdate(
            facts_to_remove=[fact["id"] for fact in before["facts"]] if removal_mode == "explicit" else [],
            new_facts=[
                *repeated,
                FactProposal(content="User prefers short answers.", category="preference", confidence=0.95),
            ],
        ),
        thread_id="preferences",
        message_id="m2",
    )
    assert len(after["facts"]) == 3
    assert all(fact in after["facts"] for fact in before["facts"])
    assert {row.key for row in service.list_semantic(ctx)} == {fact["id"] for fact in after["facts"]}


def test_d3_07_delete_canonical_and_projection_then_sync(service, ctx):
    before = initial(service, ctx)
    fact_id = next(f["id"] for f in before["facts"] if "dark" in f["content"])
    service.delete_fact(ctx, fact_id)
    service.sync_profile(ctx)
    assert not any(f["id"] == fact_id for f in service.profile(ctx)["facts"])
    assert not any(r.key == fact_id for r in service.list_semantic(ctx))
    assert len(service.profile(ctx)["facts"]) == 1


def test_d3_07_episode_delete_preserves_same_key_semantic_fact(service, ctx):
    fact = initial(service, ctx)["facts"][0]
    service.record_episode(ctx, "billing dispute", "recorded test outcome", key=fact["id"])
    assert service.delete_episode(ctx, fact["id"]) is True
    assert service.search_episodes(ctx, "billing dispute") == []
    assert any(row.key == fact["id"] for row in service.list_semantic(ctx))


def test_d1_11_complete_memory_inspection(service, ctx):
    initial(service, ctx)
    key = service.record_episode(ctx, "billing dispute", "recorded test outcome")
    service.set_procedural(ctx, {"style": "Use short paragraphs."})
    result = service.inspect_all(ctx)
    assert len(result["profile"]["facts"]) == 2
    assert result["episodic"][0]["key"] == key
    assert result["procedural"]["style"] == "Use short paragraphs."


def test_d3_08_confidence_boundaries_and_quarantine(service, ctx):
    after = save(
        service,
        ctx,
        [
            FactProposal(content=f"fact confidence {value}", confidence=value)
            for value in [0.699, 0.7, 0.819, 0.82]
        ],
    )
    assert len(after["facts"]) == 3
    assert [f["lifecycle"] for f in after["facts"]] == ["proposed", "proposed", "confirmed"]
    ordinary = service.search(ctx, "fact confidence")
    assert len(ordinary) == 1 and ordinary[0].value["confidence"] == 0.82


@pytest.mark.parametrize("failure", ["exception", "schema"])
def test_d3_09_and_oa_07_failed_extraction_preserves_memory(service, ctx, provider, checkpointer, failure):
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="every_turn"))
    app.send(ctx, "preferences", "I use dark mode and prefer US English.", "m1")
    before = copy.deepcopy(service.profile(ctx))

    def fail(*args):
        if failure == "schema":
            return {"new_facts": "invalid output"}
        raise RuntimeError("Controlled provider failure")

    provider.propose = fail
    out = app.send(ctx, "preferences", "Please keep my existing preferences.", "m2")
    assert out["trace"]["memory_update"] == "failed"
    assert out["last_sync_human_count"] == 1
    assert service.profile(ctx) == before


def test_d3_10_shared_write_permission_all_service_paths(service, ctx):
    patch = MemoryUpdate(
        new_facts=[
            FactProposal(content="Pricing answers require a disclaimer.", category="policy", confidence=0.95)
        ]
    )
    with pytest.raises(PermissionError):
        service.apply_update(ctx, patch, thread_id="policy", message_id="p1", shared=True)
    with pytest.raises(PermissionError):
        service.set_policy(ctx, "Pricing answers require a disclaimer.")
    admin = AppContext(org_id=ctx.org_id, user_id=ctx.user_id, is_admin=True)
    service.set_policy(admin, "Pricing answers require a disclaimer.")
    assert service.profile(ctx, shared=True)["facts"]
    other = AppContext(org_id="other-" + ctx.org_id, user_id=ctx.user_id)
    assert not service.profile(other, shared=True)["facts"]


@pytest.mark.parametrize("admin", [False, True])
def test_d3_10_model_cannot_grant_org_write(service, ctx, provider, checkpointer, admin):
    provider.reply = lambda *args: AssistantReply(reply="A policy was requested.", update_global_policy=True)
    provider.propose = lambda *args: MemoryUpdate(
        new_facts=[
            FactProposal(
                content="Pricing answers require a disclaimer.",
                category="policy",
                confidence=0.95,
            )
        ]
    )
    context = AppContext(org_id=ctx.org_id, user_id=ctx.user_id, is_admin=admin)
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="every_turn"))
    out = app.send(context, "policy", "Org-wide: include the pricing disclaimer.", "p1")
    assert bool(service.profile(ctx, shared=True)["facts"]) is admin
    assert out["trace"]["org_update"] == ("saved" if admin else "blocked_admin_required")


@pytest.mark.parametrize(
    "strategy,expected",
    [
        ("interval", [5]),
        ("farewell", [3]),
        ("both", [3]),
        ("every_turn", [1, 2, 3, 4, 5]),
    ],
)
def test_d3_11_strategies_and_success_counters(service, ctx, provider, checkpointer, strategy, expected):
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy=strategy))
    calls = []
    for i in range(1, 6):
        before = provider.updates
        text = "Goodbye, that's all for now." if i == 3 else f"Review billing question number {i}."
        app.send(ctx, "schedule", text, f"m{i}")
        if provider.updates > before:
            calls.append(i)
    assert calls == expected


def test_d3_11_short_messages_and_commands_do_not_trigger(service, ctx, provider, checkpointer):
    app = MemoryApplication(
        service, provider, checkpointer, Settings(sync_strategy="every_turn", min_conversation_chars=1000)
    )
    app.send(ctx, "commands", "Hi", "m1")
    assert provider.updates == 0
    app.send(ctx, "commands", "/memory list", "command1")
    assert provider.updates == 0
    assert app.inspect(ctx, "commands")["human_count"] == 1


def test_d3_12_summary_and_compaction_preserve_decisions(service, ctx, provider, checkpointer):
    provider.summarize = lambda messages: "- The user prefers dark mode.\n- The user prefers US English."
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="every_turn"))
    app.send(ctx, "summary", "I use dark mode and prefer US English.", "m1")
    before = service.profile(ctx)
    app.summarize(ctx, "summary")
    state = app.inspect(ctx, "summary")
    assert len(state["messages"]) == 1 and "US English" in state["messages"][0].content
    assert state["human_count"] == 1
    fact = before["facts"][0]
    for key in ("duplicate-a", "duplicate-b"):
        service.store.put(
            ctx.namespace("semantic"),
            key,
            {
                "fact": fact["content"],
                "mem_ix": fact["content"] + " key:" + key,
                "source_type": "profile_projection",
                "projection_of": fact["id"],
                "lifecycle": "confirmed",
            },
        )
        assert service.store.get(ctx.namespace("semantic"), key).value["fact"] == fact["content"]
    assert service.compact(ctx) == 2
    assert service.profile(ctx)["facts"] == before["facts"]
    assert len(service.search(ctx, "appearance")) == 2


def test_d3_11_schedule_survives_summary(service, ctx, provider, checkpointer):
    provider.summarize = lambda messages: "- Billing decisions are retained."
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="interval"))
    for i in range(1, 5):
        app.send(ctx, "summary-schedule", f"Review billing question {i}.", f"m{i}")
    app.summarize(ctx, "summary-schedule")
    out = app.send(ctx, "summary-schedule", "Review billing question five.", "m5")
    assert provider.updates == 1
    assert out["last_sync_human_count"] == 5
    app.send(ctx, "summary-schedule", "Review billing question 1.", "m1")
    assert provider.updates == 1 and app.inspect(ctx, "summary-schedule")["human_count"] == 5


@pytest.mark.parametrize("max_tokens", [200, 2400])
def test_d3_13_context_budget_favors_billing(service, ctx, max_tokens):
    save(
        service,
        ctx,
        [FactProposal(content="Billing duplicate charge requires invoice review.", confidence=0.95)]
        + [
            FactProposal(content=f"Unrelated background item {i}: " + "garden " * 540, confidence=0.95)
            for i in range(30)
        ],
    )
    context, ids = service.context(ctx, "billing duplicate charged refund", max_tokens=max_tokens)
    assert token_count(context) <= max_tokens
    assert "invoice review" in context and ids


def test_d3_14_corrected_and_deleted_facts_restore(ctx, service, request):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Corrected-state restart runs in the PostgreSQL verification layer.")
    from test_demo2 import child

    before = initial(service, ctx)
    after = correction(service, ctx, before)
    light_id = next(f["id"] for f in after["facts"] if "light" in f["content"])
    service.delete_fact(ctx, light_id)
    code, restored = child(ctx, "read", thread="preferences")
    assert code == 0
    assert [f["content"] for f in restored["facts"]] == ["User prefers US English."]


def test_d3_13_uses_the_chat_models_tokenizer():
    import tiktoken

    text = "मुंबई यात्रा बजट ₹20,000"
    expected = len(tiktoken.encoding_for_model("gpt-4o-mini").encode(text))
    assert token_count(text) == expected


def test_oa_07_embedding_failure_rolls_back_profile_and_search(ctx, postgres_backends, request, provider):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Database rollback runs in the PostgreSQL verification layer.")
    import os

    from conftest import fixture_embeddings
    from user_memory.service import UserMemoryService
    from user_memory.storage import open_postgres

    failure = {"enabled": False}

    def embed(texts):
        if failure["enabled"]:
            raise RuntimeError("Controlled embedding API failure")
        return [v + [0.0] * (1536 - len(v)) for v in fixture_embeddings(texts)]

    with open_postgres(
        os.environ["TEST_DATABASE_URL"], embed_texts=embed, dims=1536, test_database=True
    ) as backends:
        service = UserMemoryService(backends.store)
        before = initial(service, ctx)

        def propose(*args):
            failure["enabled"] = True
            return MemoryUpdate(
                new_facts=[FactProposal(content="A new durable billing fact.", confidence=0.95)]
            )

        provider.propose = propose
        app = MemoryApplication(
            service, provider, backends.checkpointer, Settings(sync_strategy="every_turn")
        )
        out = app.send(ctx, "embedding-failure", "Please record this billing context.", "m1")
        assert out["trace"]["memory_update"] == "failed"
    independent = UserMemoryService(postgres_backends.store)
    assert independent.profile(ctx) == before
    assert {r.key for r in independent.list_semantic(ctx)} == {f["id"] for f in before["facts"]}
