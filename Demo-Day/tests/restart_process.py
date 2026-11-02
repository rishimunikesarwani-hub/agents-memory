"""A separate application process for restart proofs. Never print credentials."""

import argparse
import json
import os
import sys

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from conftest import FixtureProvider, fixture_embeddings
from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.models import AppContext
from user_memory.service import UserMemoryService
from user_memory.storage import checkpoint_serializer, open_postgres


def run(backends, args):
    ctx = AppContext(org_id=args.org, user_id=args.user)
    service = UserMemoryService(backends.store)
    app = MemoryApplication(
        service, FixtureProvider(), backends.checkpointer, Settings(sync_strategy="every_turn")
    )
    if args.action == "seed":
        app.send(ctx, args.thread, "I use dark mode and prefer US English.", "m1")
        service.record_episode(ctx, "billing duplicate charge", "recorded test credit", key="episode-1")
        service.set_procedural(ctx, {"style": "Use short paragraphs.", "workflow": "Check the invoice."})
    elif args.action == "continue":
        app.send(ctx, args.thread, "Please review my billing issue.", "m2")
    elif args.action == "billing-seed":
        app.send(ctx, args.thread, "I was charged twice.", "m1")
        app.send(ctx, args.thread, "I'm on the Pro plan.", "m2")
    elif args.action == "billing-continue":
        app.send(ctx, args.thread, "I want a refund.", "m3")
    state = app.inspect(ctx, args.thread)
    snapshot = app.graph.get_state(app.config(ctx, args.thread))
    return {
        "pid": os.getpid(),
        "checkpoint_id": snapshot.config["configurable"].get("checkpoint_id") if snapshot.config else None,
        "messages": [{"id": m.id, "role": m.type, "content": m.content} for m in state["messages"]],
        "facts": service.profile(ctx)["facts"],
        "semantic": [
            {"key": row.key, "score": row.score, **row.value} for row in service.search(ctx, "appearance")
        ],
        "episodes": [{"key": row.key, **row.value} for row in service.search_episodes(ctx, "billing")],
        "procedural": service.procedural(ctx),
        "trace": state.get("trace", {}),
        "delivered_message_ids": state.get("delivered_message_ids", {}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "read", "continue", "billing-seed", "billing-continue"))
    parser.add_argument("--org", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--thread", default="restart")
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    Settings.from_env()
    try:
        if args.memory:
            from types import SimpleNamespace

            result = run(
                SimpleNamespace(
                    checkpointer=InMemorySaver(),
                    store=InMemoryStore(index={"dims": 4, "embed": fixture_embeddings, "fields": ["mem_ix"]}),
                ),
                args,
            )
        else:

            def embed(texts):
                return [v + [0.0] * (1536 - len(v)) for v in fixture_embeddings(texts)]

            with open_postgres(
                os.environ["TEST_DATABASE_URL"],
                embed_texts=embed,
                dims=1536,
                serde=checkpoint_serializer(),
                test_database=True,
            ) as backends:
                result = run(backends, args)
        print(json.dumps(result))
        return 0
    except Exception as exc:  # noqa: BLE001 - child errors must not expose connection details
        print(json.dumps({"pid": os.getpid(), "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
