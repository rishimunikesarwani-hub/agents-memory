import pytest
from langchain_core.messages import HumanMessage

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import AppContext, FactProposal, MemoryUpdate


def application(service, provider, checkpointer):
    return MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="every_turn"))


def seed(service, ctx):
    return service.apply_update(
        ctx,
        MemoryUpdate(
            new_facts=[
                FactProposal(content="User prefers dark mode.", category="preference", confidence=0.95),
                FactProposal(content="User prefers US English.", category="preference", confidence=0.95),
            ]
        ),
        thread_id="preferences",
        message_id="m1",
    )


def test_d1_01_new_identity_empty(service, ctx, provider, checkpointer):
    app = application(service, provider, checkpointer)
    assert service.profile(ctx)["facts"] == []
    assert app.inspect(ctx, "new")["messages"] == []


def test_d1_02_message_saved_with_id(service, ctx, provider, checkpointer):
    app = application(service, provider, checkpointer)
    out = app.send(ctx, "preferences", "I use dark mode and prefer US English.", "m1")
    state = app.inspect(ctx, "preferences")
    human = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    assert [(m.id, m.content) for m in human] == [("m1", "I use dark mode and prefer US English.")]
    assert out["trace"]["memory_update"] == "saved"


def test_d1_04_profile_has_provenance(service, ctx):
    facts = seed(service, ctx)["facts"]
    assert {f["content"] for f in facts} == {"User prefers dark mode.", "User prefers US English."}
    assert len({f["id"] for f in facts}) == 2
    assert all(f["source_thread_id"] == "preferences" and f["source_message_id"] == "m1" for f in facts)


def test_d1_05_projection_references_authoritative_ids(service, ctx):
    facts = seed(service, ctx)["facts"]
    rows = service.list_semantic(ctx)
    assert {r.value["projection_of"] for r in rows} == {f["id"] for f in facts}


def test_d1_06_vector_search(service, ctx):
    seed(service, ctx)
    results = service.search(ctx, "appearance theme", limit=6)
    assert results[0].value["fact"] == "User prefers dark mode."


def test_d1_07_new_thread_empty_but_long_term_available(service, ctx, provider, checkpointer):
    app = application(service, provider, checkpointer)
    app.send(ctx, "first", "I use dark mode and prefer US English.", "m1")
    assert app.inspect(ctx, "second")["messages"] == []
    assert service.search(ctx, "appearance")[0].value["fact"] == "User prefers dark mode."
    app.send(ctx, "second", "What appearance do I prefer?", "m2")
    assert "dark mode" in provider.prompts[-1]


@pytest.mark.parametrize("other_scope", ["user", "organization"])
def test_d1_08_scope_in_search_and_prompt(service, ctx, provider, checkpointer, other_scope):
    other = AppContext(
        org_id=ctx.org_id if other_scope == "user" else "other-" + ctx.org_id,
        user_id="other-user" if other_scope == "user" else ctx.user_id,
    )
    seed(service, ctx)
    assert service.search(other, "appearance") == []
    app = application(service, provider, checkpointer)
    app.send(other, "preferences", "What appearance do I prefer?", "m1")
    assert "User prefers dark mode." not in provider.prompts[-1]


def test_d1_09_message_and_fact_idempotence(service, ctx, provider, checkpointer):
    app = application(service, provider, checkpointer)
    app.send(ctx, "preferences", "I use dark mode and prefer US English.", "m1")
    app.send(ctx, "preferences", "I use dark mode and prefer US English.", "m1")
    assert provider.updates == 1
    assert len([m for m in app.inspect(ctx, "preferences")["messages"] if m.type == "human"]) == 1
    seed(service, ctx)
    assert len(service.profile(ctx)["facts"]) == 2


@pytest.mark.parametrize(
    "invalid",
    [
        "x" * 4001,
        "123-45-6789",
        "4111 1111 1111 1111",
        "-----BEGIN PRIVATE KEY-----",
        "AKIA1234567890ABCDEF",
        "sk-" + "x" * 30,
    ],
)
def test_d1_10_invalid_memory_never_saved(service, ctx, invalid):
    update = MemoryUpdate(new_facts=[FactProposal(content=invalid, confidence=0.95)])
    with pytest.raises(ValueError):
        service.apply_update(ctx, update, thread_id="t", message_id="m")
    assert service.profile(ctx)["facts"] == []
    assert service.list_semantic(ctx) == []


def test_d1_11_episode_scope(service, ctx):
    key = service.record_episode(ctx, "billing duplicate charge", "recorded test credit outcome")
    results = service.search_episodes(ctx, "billing refund")
    assert results[0].key == key
    assert results[0].value["outcome"] == "recorded test credit outcome"
    assert service.search_episodes(AppContext(org_id=ctx.org_id, user_id="other"), "billing") == []


def test_d1_12_procedural_partial_update(service, ctx):
    service.set_procedural(ctx, {"style": "Use bullets.", "workflow": "Verify the invoice."})
    service.set_procedural(ctx, {"style": "Use short paragraphs."})
    result = service.procedural(ctx)
    assert result["style"] == "Use short paragraphs."
    assert result["workflow"] == "Verify the invoice."


def test_d1_08_same_thread_label_other_user_has_no_transcript(service, ctx, provider, checkpointer):
    app = application(service, provider, checkpointer)
    app.send(ctx, "shared-label", "Private original message.", "private")
    other = AppContext(org_id=ctx.org_id, user_id="other")
    assert app.inspect(other, "shared-label")["messages"] == []


def test_d1_07_profile_summary_is_available_in_a_new_thread(service, ctx, provider, checkpointer):
    from user_memory.models import SectionPatch, UserPatch

    service.apply_update(
        ctx,
        MemoryUpdate(
            user=UserPatch(
                workContext=SectionPatch(
                    summary="The user investigates billing disputes for a subscription company.",
                    should_update=True,
                )
            )
        ),
        thread_id="earlier",
        message_id="profile-summary",
    )
    app = application(service, provider, checkpointer)
    assert app.inspect(ctx, "new-thread")["messages"] == []
    app.send(ctx, "new-thread", "What kind of work do I do?", "m1")
    assert "investigates billing disputes" in provider.prompts[-1]


def test_d1_11_episode_is_available_to_assistant_in_correct_scope(service, ctx, provider, checkpointer):
    service.record_episode(ctx, "billing duplicate charge", "recorded pro-rata credit test outcome")
    app = application(service, provider, checkpointer)
    app.send(ctx, "billing", "Please review a duplicate billing charge.", "m1")
    assert "recorded pro-rata credit test outcome" in provider.prompts[-1]
    other = AppContext(org_id=ctx.org_id, user_id="other-episode-reader")
    app.send(other, "billing", "Please review a duplicate billing charge.", "m1")
    assert "recorded pro-rata credit test outcome" not in provider.prompts[-1]


def test_d1_08_profile_summary_does_not_cross_user_scope(service, ctx, provider, checkpointer):
    from user_memory.models import SectionPatch, UserPatch

    service.apply_update(
        ctx,
        MemoryUpdate(
            user=UserPatch(
                workContext=SectionPatch(
                    summary="Private work context for the original user.",
                    should_update=True,
                )
            )
        ),
        thread_id="earlier",
        message_id="private-summary",
    )
    app = application(service, provider, checkpointer)
    other = AppContext(org_id=ctx.org_id, user_id="other-profile-reader")
    app.send(other, "new-thread", "What kind of work do I do?", "m1")
    assert "Private work context for the original user." not in provider.prompts[-1]
