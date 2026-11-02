import copy
import json
import re
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from functools import lru_cache

import tiktoken
from langgraph.store.base import BaseStore, PutOp

from .models import AppContext, FactProposal, MemoryUpdate

ORG_CATEGORIES = {"policy", "compliance", "legal", "disclaimer", "org_naming", "knowledge", "context"}
PROCEDURAL_FIELDS = ("style", "workflow", "safety", "task_policies")


@lru_cache(maxsize=16)
def _chat_encoding(model):
    return tiktoken.encoding_for_model(model)


def now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def validate_text(text: str, max_chars: int = 4000) -> str:
    text = text.strip()
    if not text or len(text) > max_chars:
        raise ValueError(f"Memory text must contain 1-{max_chars} characters.")
    patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b(?:\d[ -]*?){13,19}\b",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
    ]
    if any(re.search(p, text) for p in patterns) or (
        "-----begin" in text.lower() and "private key" in text.lower()
    ):
        raise ValueError("Memory text contains a prohibited sensitive-data pattern.")
    return text


def empty_profile() -> dict:
    return {
        "version": "1.0",
        "updated_at": "",
        "facts": [],
        "user": {
            k: {"summary": "", "updated_at": ""} for k in ("workContext", "personalContext", "topOfMind")
        },
        "history": {
            k: {"summary": "", "updated_at": ""}
            for k in ("recentMonths", "earlierContext", "longTermBackground")
        },
    }


def token_count(text: str, model: str = "gpt-4o-mini") -> int:
    return len(_chat_encoding(model).encode_ordinary(text))


def validate_update(update) -> MemoryUpdate:
    update = MemoryUpdate.model_validate(update)
    for fact in update.new_facts:
        validate_text(fact.content)
        if fact.evidence_span:
            validate_text(fact.evidence_span)
    for group in (update.user, update.history):
        for _, patch in group:
            if patch.should_update and patch.summary.strip():
                validate_text(patch.summary)
    return update


class UserMemoryService:
    def __init__(self, store: BaseStore):
        self.store = store

    def profile(self, ctx: AppContext, *, shared: bool = False) -> dict:
        item = self.store.get(ctx.namespace("profile", shared=shared), "document")
        return copy.deepcopy(item.value) if item else empty_profile()

    def apply_update(
        self, ctx: AppContext, update: MemoryUpdate, *, thread_id: str, message_id: str, shared: bool = False
    ) -> dict:
        if shared and not ctx.is_admin:
            raise PermissionError("Organization memory writes require an administrator.")
        update = validate_update(update)
        memory = self.profile(ctx, shared=shared)
        timestamp = now_utc()
        remove = set(update.facts_to_remove)
        for fact in update.new_facts:
            if fact.confidence >= 0.7:
                remove.update(fact.supersedes_fact_ids)
        unchanged = {
            (
                fact.content.strip().casefold(),
                fact.category,
                "confirmed" if fact.confidence >= 0.82 else "proposed",
            )
            for fact in update.new_facts
            if fact.confidence >= 0.7
        }
        memory["facts"] = [
            fact
            for fact in memory["facts"]
            if fact["id"] not in remove
            or (fact["content"].strip().casefold(), fact["category"], fact["lifecycle"]) in unchanged
        ]
        for name in ("user", "history"):
            for section, patch in getattr(update, name):
                if patch.should_update and patch.summary.strip():
                    memory[name][section] = {"summary": patch.summary.strip(), "updated_at": timestamp}
        existing = {f["content"].strip().casefold() for f in memory["facts"]}
        for fact in update.new_facts:
            content = fact.content.strip()
            if fact.confidence < 0.7 or content.casefold() in existing:
                continue
            if shared and fact.category not in ORG_CATEGORIES:
                continue
            memory["facts"].append(
                {
                    "id": "fact_" + uuid.uuid4().hex,
                    "content": content,
                    "category": fact.category,
                    "confidence": fact.confidence,
                    "lifecycle": "confirmed" if fact.confidence >= 0.82 else "proposed",
                    "needs_review": fact.confidence < 0.82,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "source_thread_id": thread_id,
                    "source_message_id": message_id,
                    "evidence_span": fact.evidence_span,
                }
            )
            existing.add(content.casefold())
        memory["updated_at"] = timestamp
        self._save_profile_and_projection(ctx, memory, shared=shared)
        return memory

    def _save_profile_and_projection(self, ctx, memory, *, shared=False):
        semantic_ns = ctx.namespace("semantic", shared=shared)
        desired = {f["id"]: f for f in memory["facts"] if f["lifecycle"] == "confirmed"}
        existing = self._list_all(semantic_ns)
        ops = [PutOp(ctx.namespace("profile", shared=shared), "document", memory, index=False)]
        for row in existing:
            if row.value.get("source_type") == "profile_projection" and row.key not in desired:
                ops.append(PutOp(semantic_ns, row.key, None))
        for fid, fact in desired.items():
            ops.append(
                PutOp(
                    semantic_ns,
                    fid,
                    {
                        "fact": fact["content"],
                        "mem_ix": fact["content"] + "\u200c" + "id:" + fid,
                        "projection_of": fid,
                        "source_type": "profile_projection",
                        "lifecycle": fact["lifecycle"],
                        "category": fact["category"],
                        "confidence": fact["confidence"],
                        "updated_at": fact["updated_at"],
                    },
                )
            )
        # Postgres uses one explicit transaction for canonical and searchable records.
        # In-memory fixtures have no durable transaction boundary.
        conn = getattr(self.store, "conn", None)
        transaction = (
            conn.transaction() if conn is not None and hasattr(conn, "transaction") else nullcontext()
        )
        with transaction:
            self.store.batch(ops)

    def _list_all(self, namespace):
        rows, offset = [], 0
        while True:
            page = list(self.store.search(namespace, limit=100, offset=offset))
            rows.extend(page)
            if len(page) < 100:
                return rows
            offset += len(page)

    def list_semantic(self, ctx):
        return self._list_all(ctx.namespace("semantic"))

    def inspect_all(self, ctx):
        return {
            "profile": self.profile(ctx),
            "organization_profile": self.profile(ctx, shared=True),
            "semantic": [{"key": row.key, **row.value} for row in self.list_semantic(ctx)],
            "episodic": [{"key": row.key, **row.value} for row in self._list_all(ctx.namespace("episodic"))],
            "procedural": self.procedural(ctx),
        }

    def delete_episode(self, ctx, key: str) -> bool:
        exists = self.store.get(ctx.namespace("episodic"), key) is not None
        self.store.delete(ctx.namespace("episodic"), key)
        return exists

    def sync_profile(self, ctx):
        self._save_profile_and_projection(ctx, self.profile(ctx))

    def delete_fact(self, ctx, fact_id: str) -> bool:
        memory = self.profile(ctx)
        existed = (
            any(f["id"] == fact_id for f in memory["facts"])
            or self.store.get(ctx.namespace("semantic"), fact_id) is not None
        )
        memory["facts"] = [f for f in memory["facts"] if f["id"] != fact_id]
        memory["updated_at"] = now_utc()
        conn = getattr(self.store, "conn", None)
        transaction = conn.transaction() if conn is not None else nullcontext()
        with transaction:
            self._save_profile_and_projection(ctx, memory)
            self.store.delete(ctx.namespace("semantic"), fact_id)
        return existed

    def compact(self, ctx) -> int:
        before = len(self.list_semantic(ctx))
        self.sync_profile(ctx)
        return max(0, before - len(self.list_semantic(ctx)))

    def set_policy(self, ctx, text: str):
        if not ctx.is_admin:
            raise PermissionError("Organization memory writes require an administrator.")
        text = validate_text(text)
        return self.apply_update(
            ctx,
            MemoryUpdate(
                new_facts=[
                    FactProposal(
                        content=text,
                        category="policy",
                        confidence=0.95,
                        evidence_span=text,
                    )
                ]
            ),
            thread_id="operator-policy",
            message_id="operator-" + uuid.uuid4().hex,
            shared=True,
        )

    def search(self, ctx, query: str, *, limit: int = 6, shared: bool = False):
        return list(
            self.store.search(
                ctx.namespace("semantic", shared=shared),
                query=query,
                filter={"lifecycle": "confirmed"},
                limit=limit,
            )
        )

    def record_episode(self, ctx, task: str, outcome: str, *, key: str | None = None):
        task, outcome = validate_text(task), validate_text(outcome)
        key = key or uuid.uuid4().hex
        self.store.put(
            ctx.namespace("episodic"),
            key,
            {
                "task": task,
                "outcome": outcome,
                "created_at": now_utc(),
                "mem_ix": task + "\n" + outcome + "\u200ckey:" + key,
            },
        )
        return key

    def search_episodes(self, ctx, query: str, *, limit: int = 3):
        return list(self.store.search(ctx.namespace("episodic"), query=query, limit=limit))

    def procedural(self, ctx):
        item = self.store.get(ctx.namespace("procedural"), "agent_instructions")
        return copy.deepcopy(item.value) if item else {k: "" for k in PROCEDURAL_FIELDS}

    def set_procedural(self, ctx, fields: dict[str, str]):
        if set(fields) - set(PROCEDURAL_FIELDS):
            raise ValueError("Unknown procedural field.")
        current = self.procedural(ctx)
        for field, value in fields.items():
            current[field] = validate_text(value) if value.strip() else ""
        current["updated_at"] = now_utc()
        self.store.put(ctx.namespace("procedural"), "agent_instructions", current, index=False)

    def context(
        self, ctx, query: str, *, max_tokens: int = 2400, model: str = "gpt-4o-mini"
    ) -> tuple[str, list[str]]:
        # Scope is always determined by the trusted context, never the model.
        user_rows = self.search(ctx, query)
        org_rows = self.search(ctx, query, shared=True)
        lines, ids = [], []
        for label, rows in (("Organization", org_rows), ("User", user_rows)):
            for row in rows:
                line = f"{label} fact [{row.key}]: {row.value['fact']}"
                if token_count("\n".join(lines + [line]), model) <= max_tokens:
                    lines.append(line)
                    ids.append(row.key)
        for label, shared in (("Organization", True), ("User", False)):
            profile = self.profile(ctx, shared=shared)
            for group in ("user", "history"):
                for section, block in profile[group].items():
                    summary = block.get("summary", "").strip()
                    if not summary:
                        continue
                    line = f"{label} profile {group}.{section}: {summary}"
                    if token_count("\n".join(lines + [line]), model) <= max_tokens:
                        lines.append(line)
        if len(query.strip()) >= 14:
            for episode in self.search_episodes(ctx, query):
                value = episode.value
                line = f"Recorded episode [{episode.key}]: task={value['task']}; outcome={value['outcome']}"
                if token_count("\n".join(lines + [line]), model) <= max_tokens:
                    lines.append(line)
                    ids.append(episode.key)
        # All text in the prompt stays within this profile injection budget.
        for label, block in (("Procedural", self.procedural(ctx)),):
            line = label + ": " + json.dumps(block, ensure_ascii=False)
            if token_count("\n".join(lines + [line]), model) <= max_tokens:
                lines.append(line)
        return "\n".join(lines), ids
