import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

from .app import MemoryApplication
from .config import Settings
from .models import AppContext, FactProposal, MemoryUpdate
from .provider import OpenAIProvider
from .service import UserMemoryService
from .storage import StorageConfigurationError, checkpoint_serializer, open_postgres


def print_json(value):
    # Redirected Windows terminals can use cp1252. ASCII JSON preserves all Unicode values.
    print(json.dumps(value, indent=2, ensure_ascii=not sys.stdout.isatty(), default=str))


def find_docker():
    found = shutil.which("docker")
    if found:
        return found
    candidates = []
    if os.getenv("LOCALAPPDATA"):
        candidates.append(
            Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin/docker.exe"
        )
    if os.getenv("ProgramFiles"):
        candidates.append(Path(os.environ["ProgramFiles"]) / "Docker/Docker/resources/bin/docker.exe")
    return next((str(path) for path in candidates if path.is_file()), None)


def parser():
    root = argparse.ArgumentParser(description="Local user-memory service. PostgreSQL + pgvector + OpenAI.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check prerequisites without printing credentials or calling OpenAI.")
    commands.add_parser("db-init", help="Initialize the new dedicated application database.")
    for name in (
        "chat",
        "turn",
        "inspect",
        "profile",
        "list",
        "search",
        "episode",
        "procedure",
        "delete",
        "correct",
        "compact",
        "summarize",
        "history",
        "policy",
        "fork",
        "replay",
    ):
        cmd = commands.add_parser(name)
        cmd.add_argument("--org", default="demo-org")
        cmd.add_argument("--user", default="alex")
        cmd.add_argument("--thread", default="demo-thread")
        cmd.add_argument(
            "--admin", action="store_true", help="Trusted local operator flag; no network access."
        )
        if name in {"chat", "turn", "inspect", "summarize", "history", "fork", "replay"}:
            cmd.add_argument(
                "--worker-mode", choices=("per_thread", "per_invocation", "stateless"), default="per_thread"
            )
            cmd.add_argument("--context-mode", choices=("unseen", "latest_only", "full"), default="unseen")
            cmd.add_argument("--delegate-after", type=int, default=1)
        if name == "inspect":
            cmd.add_argument("--worker", action="store_true")
        if name in {"fork", "replay"}:
            cmd.add_argument("checkpoint_id")
        if name == "fork":
            cmd.add_argument("text")
            cmd.add_argument("--message-id", default=None)
        if name == "turn":
            cmd.add_argument("text")
            cmd.add_argument("--message-id", default=None)
        if name == "search":
            cmd.add_argument("query")
        if name in {"profile", "search"}:
            cmd.add_argument("--shared", action="store_true")
        if name in {"delete", "correct"}:
            cmd.add_argument("fact_id")
        if name == "delete":
            cmd.add_argument("--kind", choices=("semantic", "episodic"), default="semantic")
        if name in {"correct", "policy"}:
            cmd.add_argument("text")
        if name == "episode":
            cmd.add_argument("task")
            cmd.add_argument("outcome")
            cmd.add_argument("--key", default=None)
        if name == "procedure":
            cmd.add_argument("--style")
            cmd.add_argument("--workflow")
            cmd.add_argument("--safety")
            cmd.add_argument("--task-policies")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "doctor":
        print_json(
            {
                "provider": "OpenAI",
                "openai_key_present": bool(os.getenv("OPENAI_API_KEY", "").strip()),
                "database_url_present": bool(os.getenv("DATABASE_URL", "").strip()),
                "docker_cli_present": find_docker() is not None,
                "docker_cli_on_path": shutil.which("docker") is not None,
                "chat_model": settings.chat_model,
                "memory_model": settings.memory_model,
                "embedding_model": settings.embedding_model,
                "embedding_dims": settings.embedding_dims,
                "sync_strategy": settings.sync_strategy,
                "every_n_humans": settings.every_n_humans,
            }
        )
        return 0
    try:
        if args.command == "policy" and not args.admin:
            raise PermissionError("Organization memory writes require an administrator.")
        provider = (
            OpenAIProvider(settings)
            if args.command in {"chat", "turn", "summarize", "fork", "replay"}
            else None
        )

        # Setup and inspection do not need a model key. Only actual model operations do.
        def embed_texts(texts):
            return OpenAIProvider(settings).embed_texts(texts)

        with open_postgres(
            os.getenv("DATABASE_URL", ""),
            embed_texts=embed_texts,
            dims=settings.embedding_dims,
            setup=args.command == "db-init",
            serde=checkpoint_serializer(),
        ) as backends:
            if args.command == "db-init":
                print_json({"database_setup": "complete"})
                return 0
            service = UserMemoryService(backends.store)
            ctx = AppContext(org_id=args.org, user_id=args.user, is_admin=args.admin)
            if args.command == "profile":
                print_json(service.profile(ctx, shared=args.shared))
            elif args.command == "list":
                print_json(service.inspect_all(ctx))
            elif args.command == "search":
                print_json(
                    [
                        {"id": r.key, "score": r.score, **r.value}
                        for r in service.search(ctx, args.query, shared=args.shared)
                    ]
                )
            elif args.command == "delete":
                deleted = (
                    service.delete_episode(ctx, args.fact_id)
                    if args.kind == "episodic"
                    else service.delete_fact(ctx, args.fact_id)
                )
                print_json({"deleted": deleted, "kind": args.kind})
            elif args.command == "correct":
                previous = next((f for f in service.profile(ctx)["facts"] if f["id"] == args.fact_id), None)
                if previous is None:
                    print("Fact identifier was not found.", file=sys.stderr)
                    return 2
                result = service.apply_update(
                    ctx,
                    MemoryUpdate(
                        facts_to_remove=[args.fact_id],
                        new_facts=[
                            FactProposal(
                                content=args.text,
                                category=previous["category"],
                                confidence=0.95,
                                supersedes_fact_ids=[args.fact_id],
                                evidence_span=args.text,
                            )
                        ],
                    ),
                    thread_id=args.thread,
                    message_id="operator-" + uuid.uuid4().hex,
                )
                print_json(result)
            elif args.command == "compact":
                print_json({"redundant_rows_removed": service.compact(ctx)})
            elif args.command == "policy":
                print_json(service.set_policy(ctx, args.text))
            elif args.command == "episode":
                print_json(
                    {
                        "recorded_test_outcome_id": service.record_episode(
                            ctx, args.task, args.outcome, key=args.key
                        )
                    }
                )
            elif args.command == "procedure":
                fields = {
                    k: getattr(args, k)
                    for k in ("style", "workflow", "safety", "task_policies")
                    if getattr(args, k) is not None
                }
                if fields:
                    service.set_procedural(ctx, fields)
                print_json(service.procedural(ctx))
            else:
                app = MemoryApplication(
                    service,
                    provider,
                    backends.checkpointer,
                    settings,
                    worker_mode=args.worker_mode,
                    context_mode=args.context_mode,
                    delegate_after=args.delegate_after,
                )
                if args.command == "inspect":
                    state = (
                        app.inspect_worker(ctx, args.thread) if args.worker else app.inspect(ctx, args.thread)
                    )
                    state["messages"] = [
                        {"id": m.id, "role": m.type, "content": m.content} for m in state["messages"]
                    ]
                    print_json(state)
                elif args.command == "fork":
                    show_turn(
                        app.fork(
                            ctx,
                            args.thread,
                            args.checkpoint_id,
                            args.text,
                            args.message_id or uuid.uuid4().hex,
                        )
                    )
                elif args.command == "replay":
                    show_turn(app.replay(ctx, args.thread, args.checkpoint_id))
                elif args.command == "summarize":
                    state = app.summarize(ctx, args.thread)
                    print_json(
                        {
                            "message_count": len(state["messages"]),
                            "summary": state["messages"][-1].content if state["messages"] else "",
                        }
                    )
                elif args.command == "history":
                    print_json(
                        [
                            {
                                "checkpoint_id": s.config["configurable"]["checkpoint_id"],
                                "next": s.next,
                                "step": s.metadata.get("step"),
                            }
                            for s in app.graph.get_state_history(app.config(ctx, args.thread))
                        ]
                    )
                elif args.command == "turn":
                    show_turn(app.send(ctx, args.thread, args.text, args.message_id or uuid.uuid4().hex))
                elif args.command == "chat":
                    print(
                        f"Thread: {args.thread}; extraction: {settings.sync_strategy}. Enter /exit to close."
                    )
                    while True:
                        try:
                            text = input("You: ").strip()
                        except (EOFError, KeyboardInterrupt):
                            break
                        if text == "/exit":
                            break
                        if text:
                            show_turn(app.send(ctx, args.thread, text, uuid.uuid4().hex))
    except Exception as exc:  # noqa: BLE001 - redact dependency errors at the CLI boundary
        # Exception strings from dependencies can include connection strings or request headers.
        code = type(exc).__name__
        if isinstance(exc, ValueError) and "OPENAI_API_KEY" in str(exc):
            print("Set OPENAI_API_KEY in your local environment or excluded .env file.", file=sys.stderr)
        elif isinstance(exc, StorageConfigurationError):
            print(str(exc), file=sys.stderr)
        else:
            print(
                f"Operation failed ({code}). Check local configuration and service availability.",
                file=sys.stderr,
            )
        return 1
    return 0


def show_turn(state):
    answer = next(m.content for m in reversed(state["messages"]) if m.type == "ai")
    print_json({"answer": answer, "trace": state["trace"]})
