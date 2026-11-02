import hashlib
import json
import shlex
import uuid
from contextlib import nullcontext
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .config import Settings
from .models import AppContext, valid_id
from .service import UserMemoryService, validate_text, validate_update
from .worker import build_worker


class ParentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    processed_ids: list[str]
    human_count: int
    last_sync_human_count: int
    trace: dict
    input_hashes: dict[str, str]
    update_global_policy: bool
    pending_org_policy: bool
    delivered_message_ids: dict[str, list[str]]
    worker_namespaces: dict[str, str]


def normal_messages(messages):
    return [
        m
        for m in messages
        if not m.response_metadata.get("command")
        and not (m.type == "human" and str(m.content).strip().startswith("/"))
    ]


def memory_update_due(state, settings):
    messages = normal_messages(state["messages"])
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages)
    if len(transcript) < settings.min_conversation_chars:
        return False
    humans = [m for m in messages if m.type == "human" and str(m.content).strip()]
    if not humans:
        return False
    farewell = any(token in str(humans[-1].content).lower() for token in settings.farewell_triggers)
    interval = state.get("human_count", 0) - state.get("last_sync_human_count", 0) >= settings.every_n_humans
    return {"every_turn": True, "interval": interval, "farewell": farewell, "both": farewell or interval}[
        settings.sync_strategy
    ]


class MemoryApplication:
    """One parent coordinates one worker and a scoped long-term memory service."""

    def __init__(
        self,
        service: UserMemoryService,
        provider,
        checkpointer,
        settings: Settings,
        *,
        worker_mode: str = "per_thread",
        context_mode: str = "unseen",
        delegate_after: int = 1,
        worker_id: str = "billing",
    ):
        self.service, self.provider, self.settings = service, provider, settings
        self.checkpointer = checkpointer
        valid_id(worker_id)
        if context_mode not in {"unseen", "latest_only", "full"} or delegate_after < 1:
            raise ValueError("Invalid worker context strategy or delegation threshold.")
        self.worker_id = worker_id
        self.worker = build_worker(service, provider, settings, mode=worker_mode, worker_id=worker_id)
        response_node = "respond_" + worker_id

        def respond(state: ParentState, config):
            ctx = AppContext(**config["configurable"]["identity"])
            human = next(m for m in reversed(state["messages"]) if isinstance(m, HumanMessage))
            count = state.get("human_count", 0) + 1
            delivered = {key: list(value) for key, value in state.get("delivered_message_ids", {}).items()}
            namespaces = dict(state.get("worker_namespaces", {}))
            if count >= delegate_after:
                history = normal_messages(state["messages"])
                seen = set(delivered.get(worker_id, []))
                payload = (
                    [human]
                    if context_mode == "latest_only"
                    else history
                    if context_mode == "full"
                    else [m for m in history if m.id not in seen]
                )
                result = self.worker.invoke(
                    {"messages": payload, "supplied_ids": [m.id for m in payload]}, config=config
                )
                message = result["messages"][-1]
                delivered[worker_id] = list(
                    dict.fromkeys([*delivered.get(worker_id, []), *[m.id for m in payload], message.id])
                )
                trace = {**result["observation"], "memory_update": "not_due", "graph": "parent"}
                namespaces[worker_id] = trace["worker_namespace"]
                global_policy = result.get("update_global_policy", False)
            else:
                context, ids = service.context(
                    ctx, str(human.content), max_tokens=settings.profile_max_tokens, model=settings.chat_model
                )
                reply = provider.reply(normal_messages(state["messages"]), context)
                message = AIMessage(content=reply.reply, id="answer-" + human.id)
                global_policy = reply.update_global_policy
                trace = {
                    "worker_called": False,
                    "retrieved_memory_ids": ids,
                    "memory_update": "not_due",
                    "supplied_message_ids": [],
                    "graph": "parent",
                }
            return {
                "messages": [message],
                "human_count": count,
                "update_global_policy": global_policy,
                "delivered_message_ids": delivered,
                "worker_namespaces": namespaces,
                "trace": trace,
            }

        def persist(state: ParentState, config):
            ctx = AppContext(**config["configurable"]["identity"])
            human = next(m for m in reversed(state["messages"]) if isinstance(m, HumanMessage))
            count = state["human_count"]
            trace = dict(state["trace"])
            processed = [*state.get("processed_ids", []), human.id]
            requested = bool(state.get("pending_org_policy") or state.get("update_global_policy"))
            allowed = requested and ctx.is_admin
            trace["org_update"] = (
                "pending_sync" if allowed else "blocked_admin_required" if requested else "not_requested"
            )
            result = {
                "processed_ids": processed,
                "trace": trace,
                "pending_org_policy": allowed,
                "update_global_policy": False,
            }
            if memory_update_due(state, settings):
                try:
                    messages = normal_messages(state["messages"])
                    update = validate_update(provider.propose(messages, service.profile(ctx), "user"))
                    org_update = (
                        validate_update(provider.propose(messages, service.profile(ctx, shared=True), "org"))
                        if allowed
                        else None
                    )
                    conn = getattr(service.store, "conn", None)
                    transaction = conn.transaction() if conn is not None else nullcontext()
                    with transaction:
                        service.apply_update(
                            ctx,
                            update,
                            thread_id=config["configurable"]["conversation_id"],
                            message_id=human.id,
                        )
                        if org_update is not None:
                            service.apply_update(
                                ctx,
                                org_update,
                                thread_id=config["configurable"]["conversation_id"],
                                message_id=human.id,
                                shared=True,
                            )
                except Exception:  # noqa: BLE001 - redact errors at the external provider/storage boundary
                    trace["memory_update"] = "failed"
                    return result
                trace["memory_update"] = "saved"
                if org_update is not None:
                    trace["org_update"] = "saved"
                result.update(last_sync_human_count=count, pending_org_policy=False)
            return result

        def commands(state, config):
            ctx = AppContext(**config["configurable"]["identity"])
            human = next(m for m in reversed(state["messages"]) if isinstance(m, HumanMessage))
            try:
                parts = shlex.split(str(human.content))
                if parts[:2] == ["/thread", "summarize"]:
                    result = self._summary_update(state)
                else:
                    if parts[:2] == ["/memory", "list"]:
                        text = json.dumps(service.inspect_all(ctx), ensure_ascii=False)
                    elif parts[:3] == ["/memory", "delete", "semantic"] and len(parts) == 4:
                        text = json.dumps({"deleted": service.delete_fact(ctx, parts[3])})
                    elif parts[:3] == ["/memory", "delete", "episodic"] and len(parts) == 4:
                        text = json.dumps({"deleted": service.delete_episode(ctx, parts[3])})
                    elif parts[:2] == ["/memory", "compact"]:
                        text = json.dumps({"redundant_rows_removed": service.compact(ctx)})
                    elif parts[:2] == ["/proc", "set"] and len(parts) > 2:
                        service.set_procedural(ctx, {"style": " ".join(parts[2:])})
                        text = "Procedural style saved."
                    else:
                        text = "Unknown command. Use /memory list or /thread summarize."
                    result = {
                        "messages": [
                            AIMessage(
                                content=text, id="answer-" + human.id, response_metadata={"command": True}
                            )
                        ]
                    }
            except ValueError:
                result = {
                    "messages": [
                        AIMessage(
                            content="Invalid command input.",
                            id="answer-" + human.id,
                            response_metadata={"command": True},
                        )
                    ]
                }
            result.update(
                processed_ids=[*state.get("processed_ids", []), human.id],
                trace={"memory_update": "command", "graph": "parent"},
            )
            return result

        graph = StateGraph(ParentState)
        graph.add_node(response_node, respond)
        graph.add_node("persist", persist)
        graph.add_node("commands", commands)
        graph.add_conditional_edges(
            START,
            lambda state: (
                "commands" if str(state["messages"][-1].content).strip().startswith("/") else response_node
            ),
        )
        graph.add_edge("commands", END)
        graph.add_edge(response_node, "persist")
        graph.add_edge("persist", END)
        self.graph = graph.compile(checkpointer=checkpointer, store=service.store)

    def config(self, ctx: AppContext, thread_id: str):
        valid_id(thread_id)
        identity = {"org_id": ctx.org_id, "user_id": ctx.user_id, "is_admin": ctx.is_admin}
        scoped = hashlib.sha256(json.dumps([ctx.org_id, ctx.user_id, thread_id]).encode()).hexdigest()
        return {"configurable": {"thread_id": scoped, "conversation_id": thread_id, "identity": identity}}

    def inspect(self, ctx: AppContext, thread_id: str) -> dict:
        values = dict(self.graph.get_state(self.config(ctx, thread_id)).values)
        values.setdefault("messages", [])
        return values

    def inspect_worker(self, ctx: AppContext, thread_id: str) -> dict:
        parent = self.inspect(ctx, thread_id)
        namespace = parent.get("worker_namespaces", {}).get(self.worker_id)
        if not namespace:
            return {"messages": []}
        config = self.config(ctx, thread_id)
        config["configurable"]["checkpoint_ns"] = namespace
        item = self.checkpointer.get_tuple(config)
        return dict(item.checkpoint["channel_values"]) if item else {"messages": []}

    def send(self, ctx: AppContext, thread_id: str, text: str, message_id: str):
        valid_id(message_id)
        validate_text(text, max_chars=16000)
        config = self.config(ctx, thread_id)
        previous = self.inspect(ctx, thread_id)
        digest = hashlib.sha256(text.encode()).hexdigest()
        hashes = dict(previous.get("input_hashes", {}))
        if message_id in hashes and hashes[message_id] != digest:
            raise ValueError("A message ID cannot be reused with different content.")
        if message_id in previous.get("processed_ids", []):
            return previous
        old = next((m for m in previous["messages"] if m.id == message_id), None)
        if old is not None:
            if old.content != text:
                raise ValueError("A message ID cannot be reused with different content.")
            if message_id in previous.get("processed_ids", []):
                return previous
        hashes[message_id] = digest
        return self.graph.invoke(
            {"messages": [HumanMessage(content=text, id=message_id)], "input_hashes": hashes}, config
        )

    def _summary_update(self, state):
        messages = normal_messages(state["messages"])
        summary = validate_text(self.provider.summarize(messages), max_chars=16000)
        removes = [RemoveMessage(id=m.id) for m in state["messages"] if m.id]
        return {
            "messages": removes
            + [
                AIMessage(
                    content="Historical conversation summary:\n" + summary,
                    id="summary-" + uuid.uuid4().hex,
                    response_metadata={"synthetic_summary": True},
                )
            ]
        }

    def summarize(self, ctx, thread_id):
        state = self.inspect(ctx, thread_id)
        if state["messages"]:
            self.graph.update_state(
                self.config(ctx, thread_id), self._summary_update(state), as_node="persist"
            )
        return self.inspect(ctx, thread_id)

    def _checkpoint_config(self, ctx, thread_id, checkpoint_id):
        config = self.config(ctx, thread_id)
        config["configurable"]["checkpoint_id"] = checkpoint_id
        config["configurable"]["checkpoint_ns"] = ""
        if not self.graph.get_state(config).created_at:
            raise ValueError("Checkpoint was not found in this conversation scope.")
        return config

    def fork(self, ctx, thread_id, checkpoint_id, text, message_id):
        valid_id(message_id)
        validate_text(text, max_chars=16000)
        config = self._checkpoint_config(ctx, thread_id, checkpoint_id)
        state = self.graph.get_state(config).values
        hashes = {**state.get("input_hashes", {}), message_id: hashlib.sha256(text.encode()).hexdigest()}
        forked = self.graph.update_state(
            config,
            {"messages": [HumanMessage(content=text, id=message_id)], "input_hashes": hashes},
            as_node=START,
        )
        # update_state returns checkpoint coordinates, so reattach the trusted invocation context.
        forked["configurable"].update(
            {key: value for key, value in config["configurable"].items() if key != "checkpoint_id"}
        )
        return self.graph.invoke(None, forked)

    def replay(self, ctx, thread_id, checkpoint_id):
        return self.graph.invoke(None, self._checkpoint_config(ctx, thread_id, checkpoint_id))
