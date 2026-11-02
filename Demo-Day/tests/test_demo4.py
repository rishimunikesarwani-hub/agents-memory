import copy

import pytest

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import FactProposal, MemoryUpdate

TURNS = ["I was charged twice.", "I'm on the Pro plan.", "I want a refund."]
ALL_KNOWN = {"issue": "duplicate", "tier": "pro", "action": "refund"}


def build(service, provider, checkpointer, **options):
    return MemoryApplication(service, provider, checkpointer, Settings(every_n_humans=1000), **options)


def three(app, ctx, thread="billing"):
    return [copy.deepcopy(app.send(ctx, thread, text, f"m{i}")["trace"]) for i, text in enumerate(TURNS, 1)]


def test_d4_01_worker_called_once_per_turn(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer)
    traces = three(app, ctx)
    assert [t["worker_called"] for t in traces] == [True, True, True]
    assert len(provider.prompts) == 3


def test_d4_02_parent_supplies_latest_only_in_comparison(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer, context_mode="latest_only")
    traces = three(app, ctx)
    assert [t["supplied_message_ids"] for t in traces] == [["m1"], ["m2"], ["m3"]]


def test_d4_03_per_thread_restores_earlier_messages(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer, context_mode="latest_only")
    traces = three(app, ctx)
    assert [t["pre_reply_count"] for t in traces] == [1, 3, 5]
    assert traces[-1]["known"] == ALL_KNOWN
    assert {"m1", "m2"}.issubset(traces[-1]["restored_message_ids"])


@pytest.mark.parametrize("mode", ["per_invocation", "stateless"])
def test_d4_04_fresh_worker_does_not_recover_missing_history(service, ctx, provider, checkpointer, mode):
    app = build(service, provider, checkpointer, worker_mode=mode, context_mode="latest_only")
    traces = three(app, ctx)
    assert [t["pre_reply_count"] for t in traces] == [1, 1, 1]
    assert traces[-1]["known"] == {"issue": None, "tier": None, "action": "refund"}


def test_d4_05_parent_and_worker_have_separate_checkpoints(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer)
    traces = three(app, ctx)
    parent = app.graph.get_state(app.config(ctx, "billing"))
    worker_ns = traces[-1]["worker_namespace"]
    assert worker_ns and worker_ns != parent.config["configurable"].get("checkpoint_ns", "")
    namespaces = {
        item.config["configurable"].get("checkpoint_ns", "")
        for item in checkpointer.list(app.config(ctx, "billing"))
    }
    assert "" in namespaces and worker_ns in namespaces
    worker_state = app.inspect_worker(ctx, "billing")
    assert len(worker_state["messages"]) == 6
    assert "human_count" not in worker_state


def test_d4_06_late_worker_without_briefing_cannot_know_earlier_turns(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer, delegate_after=3, context_mode="latest_only")
    traces = three(app, ctx)
    assert [t["worker_called"] for t in traces] == [False, False, True]
    assert traces[-1]["known"] == {"issue": None, "tier": None, "action": "refund"}


def test_d4_07_parent_explicitly_briefs_late_worker(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer, delegate_after=3)
    traces = three(app, ctx)
    assert traces[-1]["known"] == ALL_KNOWN
    assert {"m1", "m2", "m3"}.issubset(traces[-1]["supplied_message_ids"])


def test_d4_08_repeated_briefing_uses_message_id_deduplication(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer, context_mode="full")
    traces = three(app, ctx)
    assert [t["pre_reply_count"] for t in traces] == [1, 3, 5]
    assert len(traces[-1]["state_message_ids"]) == len(set(traces[-1]["state_message_ids"]))


def test_d4_09_thread_and_worker_namespace_isolation(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer, context_mode="latest_only")
    original = three(app, ctx)[-1]
    new_thread = app.send(ctx, "new-billing-thread", TURNS[-1], "m4")["trace"]
    assert new_thread["pre_reply_count"] == 1 and new_thread["restored_message_ids"] == []
    other_worker = build(
        service, provider, checkpointer, worker_id="other-billing", context_mode="latest_only"
    )
    other = other_worker.send(ctx, "billing", TURNS[-1], "m4")["trace"]
    assert other["pre_reply_count"] == 1 and other["restored_message_ids"] == []
    assert other["worker_namespace"] != original["worker_namespace"]


def test_d4_10_and_d4_11_parent_worker_restart_and_delivery_tracking(ctx, postgres_backends, request):
    if request.config.getoption("--backend") != "postgres":
        pytest.skip("Parent-worker process restart runs in the PostgreSQL verification layer.")
    from test_demo2 import child

    first_code, first = child(ctx, "billing-seed")
    second_code, second = child(ctx, "billing-continue")
    assert first_code == second_code == 0
    assert first["pid"] != second["pid"]
    assert [m["id"] for m in second["messages"] if m["role"] == "human"] == ["m1", "m2", "m3"]
    assert second["trace"]["pre_reply_count"] == 5
    assert second["trace"]["known"] == ALL_KNOWN
    assert second["trace"]["supplied_message_ids"] == ["m3"]
    assert {"m1", "m2", "m3"}.issubset(second["delivered_message_ids"]["billing"])


def test_d4_12_fork_and_replay_preserve_history_but_not_rollback_store(service, ctx, provider, checkpointer):
    app = build(service, provider, checkpointer)
    app.send(ctx, "branch", TURNS[0], "m1")
    first_config = app.graph.get_state(app.config(ctx, "branch")).config
    app.send(ctx, "branch", TURNS[1], "m2")
    original = app.graph.get_state(app.config(ctx, "branch"))
    service.apply_update(
        ctx,
        MemoryUpdate(
            new_facts=[
                FactProposal(
                    content="Current long-term appearance is light mode.",
                    confidence=0.95,
                )
            ]
        ),
        thread_id="external",
        message_id="external-change",
    )
    before = service.profile(ctx)
    forked = app.fork(
        ctx, "branch", first_config["configurable"]["checkpoint_id"], "Please review an invoice.", "fork1"
    )
    assert [m.id for m in forked["messages"] if m.type == "human"] == ["m1", "fork1"]
    assert "m2" not in forked["trace"]["state_message_ids"]
    assert app.graph.get_state(original.config).values["messages"] == original.values["messages"]
    assert service.profile(ctx) == before
    before_persist = next(
        s for s in app.graph.get_state_history(app.config(ctx, "branch")) if s.next == ("persist",)
    )
    app.replay(ctx, "branch", before_persist.config["configurable"]["checkpoint_id"])
    assert service.profile(ctx) == before
