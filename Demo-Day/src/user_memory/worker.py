"""A billing subgraph with private messages and a separate checkpoint namespace."""

import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .models import AppContext


class WorkerState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    supplied_ids: list[str]
    observation: dict
    update_global_policy: bool


def build_worker(service, provider, settings, *, mode: str, worker_id: str):
    modes = {"per_invocation": None, "per_thread": True, "stateless": False}
    if mode not in modes:
        raise ValueError("Invalid worker mode.")

    def billing_worker(state, config):
        ctx = AppContext(**config["configurable"]["identity"])
        humans = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        texts = [str(m.content).lower() for m in humans]
        # Deterministic findings explain the book fixture. The model supplies the actual answer.
        known = {
            "issue": "duplicate" if any("charged twice" in text for text in texts) else None,
            "tier": "pro" if any("pro plan" in text for text in texts) else None,
            "action": "refund" if any("refund" in text for text in texts) else None,
        }
        context, ids = service.context(
            ctx, str(humans[-1].content), max_tokens=settings.profile_max_tokens, model=settings.chat_model
        )
        reply = provider.reply(state["messages"], context)
        supplied = state.get("supplied_ids", [])
        message_ids = [m.id for m in state["messages"]]
        task_namespace = config["configurable"].get("checkpoint_ns", "")
        graph_namespace = task_namespace.rsplit("|", 1)[0] if "|" in task_namespace else task_namespace
        observation = {
            "worker_called": True,
            "worker_id": worker_id,
            "worker_mode": mode,
            "worker_namespace": graph_namespace,
            "worker_task_namespace": task_namespace,
            "supplied_message_ids": supplied,
            "restored_message_ids": [mid for mid in message_ids if mid not in supplied],
            "state_message_ids": message_ids,
            "pre_reply_count": len(state["messages"]),
            "known": known,
            "retrieved_memory_ids": ids,
        }
        return {
            "messages": [AIMessage(content=reply.reply, id="worker-" + uuid.uuid4().hex)],
            "observation": observation,
            "update_global_policy": reply.update_global_policy,
        }

    builder = StateGraph(WorkerState)
    builder.add_node("billing_worker", billing_worker)
    builder.add_edge(START, "billing_worker")
    builder.add_edge("billing_worker", END)
    return builder.compile(checkpointer=modes[mode], name=worker_id)
