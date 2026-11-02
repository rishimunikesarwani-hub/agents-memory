"""Deterministic policy enforcement for the local memory experiment.

The principal and provenance fields are trusted runtime inputs. This module does
not authenticate users or validate factual truth. An optional hybrid retriever
ranks eligible records after the access and validity checks.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterable


KINDS = frozenset({"fact", "preference", "episode", "procedure", "lesson"})
SOURCES = frozenset({"user", "verified_tool", "admin", "untrusted_document", "reflection"})
AUTHORITY = {"admin": 3, "user": 2, "verified_tool": 1, "reflection": 0, "untrusted_document": -1}
MAX_VALUE_CHARS = 6000
STOPWORDS = frozenset("a an and are as at be by can do for from has have how i in is it me my of on or our please report should that the their this to use was what when which with would your".split())
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:/-]{1,200}$")
SECRET_PATTERNS = (
    re.compile(r"SYNTHETIC_SECRET[A-Za-z0-9_=-]*", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN[^\n]*PRIVATE KEY", re.I),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
)


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _terms(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", value.casefold()) if t not in STOPWORDS}


class MemoryStore:
    """SQLite records, write audit, and separate thread checkpoints."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path, timeout=15)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS memory (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                workflow TEXT NOT NULL,
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                observed_at INTEGER NOT NULL,
                expires_at INTEGER,
                pinned INTEGER NOT NULL,
                evidence_ids TEXT NOT NULL,
                validated INTEGER NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS memory_scope_key
                ON memory(user_id, workflow, kind, key, status);
            CREATE TABLE IF NOT EXISTS audit_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                details TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                state TEXT NOT NULL,
                memory_revision INTEGER NOT NULL,
                PRIMARY KEY (user_id, thread_id)
            );
        """)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    @staticmethod
    def _principal(principal: dict[str, Any]) -> tuple[str, str]:
        if not isinstance(principal, dict):
            raise ValueError("principal must be a runtime-supplied dictionary")
        user = principal.get("user_id")
        role = principal.get("role", "user")
        if not isinstance(user, str) or not IDENTIFIER.fullmatch(user):
            raise ValueError("invalid principal user_id")
        if role not in {"user", "admin"}:
            raise ValueError("invalid principal role")
        return user, role

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["pinned"] = bool(result["pinned"])
        result["validated"] = bool(result["validated"])
        result["evidence_ids"] = json.loads(result["evidence_ids"])
        return result

    def records(self) -> list[dict[str, Any]]:
        """Administrative experiment inspection, not a tenant-facing endpoint."""
        return [self._row(row) for row in self.connection.execute("SELECT * FROM memory ORDER BY rowid")]

    def events(self) -> list[dict[str, Any]]:
        result = []
        for row in self.connection.execute("SELECT * FROM audit_events ORDER BY sequence"):
            event = dict(row)
            event["details"] = json.loads(event["details"])
            result.append(event)
        return result

    def _audit(self, identifier: Any, status: str, reason: str, **details: Any) -> dict[str, Any]:
        safe_id = identifier if isinstance(identifier, str) and IDENTIFIER.fullmatch(identifier) and not _contains_secret(identifier) else "[redacted-invalid-id]"
        result = {"status": status, "reason": reason, "id": safe_id}
        self.connection.execute(
            "INSERT INTO audit_events(id,status,reason,details) VALUES(?,?,?,?)",
            (safe_id, status, reason, json.dumps(details, sort_keys=True)),
        )
        return result

    def _validate(self, candidate: Any, principal: dict[str, Any], now: int | None = None) -> str | None:
        user, role = self._principal(principal)
        if not isinstance(candidate, dict):
            return "malformed_candidate"
        # Scan all supplied content before storing any portion of the record.
        try:
            serialized = json.dumps(candidate, ensure_ascii=False)
        except (TypeError, ValueError):
            return "malformed_candidate"
        if _contains_secret(serialized):
            return "sensitive_content"
        for field in ("id", "workflow", "key"):
            if not isinstance(candidate.get(field), str) or not IDENTIFIER.fullmatch(candidate[field]):
                return "invalid_" + field
        target = candidate.get("user_id")
        if not isinstance(target, str) or (target != "*" and not IDENTIFIER.fullmatch(target)):
            return "invalid_user_id"
        if target != user and role != "admin":
            return "unauthorized_scope"
        if target == "*" and role != "admin":
            return "unauthorized_shared_write"
        if candidate.get("kind") not in KINDS or candidate.get("source") not in SOURCES:
            return "invalid_kind_or_source"
        if candidate["source"] == "admin" and role != "admin":
            return "unauthorized_admin_source"
        value = candidate.get("value")
        if not isinstance(value, str) or not value.strip():
            return "blank_value"
        if len(value) > MAX_VALUE_CHARS:
            return "oversized_value"
        observed = candidate.get("observed_at")
        expires = candidate.get("expires_at")
        if type(observed) is not int or observed < 0:
            return "invalid_observed_at"
        if now is not None:
            if type(now) is not int or now < 0:
                return "invalid_runtime_time"
            if observed > now:
                return "future_observation"
        if expires is not None and (type(expires) is not int or expires <= observed):
            return "invalid_expires_at"
        if type(candidate.get("validated")) is not bool:
            return "invalid_validation_metadata"
        if type(candidate.get("pinned", False)) is not bool:
            return "invalid_pinned_metadata"
        evidence = candidate.get("evidence_ids", [])
        if not isinstance(evidence, list) or not all(isinstance(x, str) and IDENTIFIER.fullmatch(x) for x in evidence):
            return "invalid_evidence_ids"
        return None

    def _insert(self, candidate: dict[str, Any], status: str, reason: str) -> None:
        self.connection.execute(
            "INSERT INTO memory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                candidate["id"], candidate["user_id"], candidate["workflow"],
                candidate["kind"], candidate["key"], candidate["value"].strip(),
                candidate["source"], candidate["observed_at"], candidate.get("expires_at"),
                int(candidate.get("pinned", False) and candidate["kind"] in {"preference", "procedure"}),
                json.dumps(candidate.get("evidence_ids", [])), int(candidate["validated"]),
                status, reason,
            ),
        )

    def _lesson_evidence_valid(self, candidate: dict[str, Any]) -> bool:
        evidence = candidate.get("evidence_ids", [])
        if not evidence:
            return False
        for identifier in evidence:
            row = self.connection.execute("SELECT * FROM memory WHERE id=?", (identifier,)).fetchone()
            if not row or row["status"] not in {"active", "superseded"} or not row["validated"]:
                return False
            if row["kind"] != "episode" or row["source"] not in {"admin", "user", "verified_tool"}:
                return False
            if row["user_id"] not in {candidate["user_id"], "*"} or row["workflow"] not in {candidate["workflow"], "shared"}:
                return False
            if row["observed_at"] > candidate["observed_at"]:
                return False
        return True

    def ingest(self, candidate: dict[str, Any], principal: dict[str, Any], *, now: int | None = None) -> dict[str, Any]:
        """Apply a candidate atomically. Omitted now trusts caller chronology."""
        identifier = candidate.get("id") if isinstance(candidate, dict) else None
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            validation = self._validate(candidate, principal, now)
            if validation:
                result = self._audit(identifier, "rejected", validation)
            else:
                result = self._ingest_valid(candidate)
            self.connection.commit()
            return result
        except BaseException:
            self.connection.rollback()
            raise

    def _ingest_valid(self, candidate: dict[str, Any]) -> dict[str, Any]:
        identifier = candidate["id"]
        collision = self.connection.execute("SELECT * FROM memory WHERE id=?", (identifier,)).fetchone()
        if collision:
            fields = ("user_id", "workflow", "kind", "key", "value", "source", "observed_at", "expires_at")
            same = all(collision[field] == candidate.get(field) for field in fields)
            return self._audit(identifier, "duplicate" if same else "rejected", "idempotent_replay" if same else "id_conflict")

        quarantine = None
        if candidate["source"] == "untrusted_document":
            quarantine = "untrusted_source"
        elif not candidate["validated"]:
            quarantine = "not_validated"
        elif candidate["source"] == "reflection":
            if candidate["kind"] != "lesson":
                quarantine = "reflection_cannot_set_policy"
            elif not self._lesson_evidence_valid(candidate):
                quarantine = "invalid_lesson_evidence"
        if quarantine:
            self._insert(candidate, "quarantined", quarantine)
            return self._audit(identifier, "quarantined", quarantine)

        current = self.connection.execute(
            "SELECT * FROM memory WHERE user_id=? AND workflow=? AND kind=? AND key=? AND status='active'",
            (candidate["user_id"], candidate["workflow"], candidate["kind"], candidate["key"]),
        ).fetchone()
        if current:
            same_value = _normalized(current["value"]) == _normalized(candidate["value"])
            same_validity = current["expires_at"] == candidate.get("expires_at")
            if same_value and same_validity:
                return self._audit(identifier, "duplicate", "same_active_value", existing_id=current["id"])
            if candidate["observed_at"] < current["observed_at"]:
                return self._audit(identifier, "rejected", "stale_update", existing_id=current["id"])
            if candidate["observed_at"] == current["observed_at"]:
                self._insert(candidate, "quarantined", "equal_time_conflict")
                return self._audit(identifier, "quarantined", "equal_time_conflict", existing_id=current["id"])
            if AUTHORITY[candidate["source"]] < AUTHORITY[current["source"]]:
                self._insert(candidate, "quarantined", "lower_authority_conflict")
                return self._audit(identifier, "quarantined", "lower_authority_conflict", existing_id=current["id"])
            self.connection.execute("UPDATE memory SET status='superseded',reason='replaced_by:' || ? WHERE id=?", (identifier, current["id"]))
        self._insert(candidate, "active", "validated_write")
        return self._audit(identifier, "accepted", "validated_write", superseded_id=current["id"] if current else None)

    def disable_lesson(self, identifier: str, principal: dict[str, Any], reason: str = "validation_regression") -> dict[str, Any]:
        """Disable an active lesson without deleting its evidence or write audit."""
        user, role = self._principal(principal)
        if reason not in {"validation_regression", "manual_rollback", "superseded_lesson"}:
            raise ValueError("unsupported lesson rollback reason")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute("SELECT * FROM memory WHERE id=?", (identifier,)).fetchone()
            if not row:
                result = self._audit(identifier, "rejected", "lesson_not_found")
            elif row["user_id"] != user and role != "admin":
                result = self._audit(identifier, "rejected", "unauthorized_scope")
            elif row["kind"] != "lesson" or row["status"] != "active":
                result = self._audit(identifier, "rejected", "not_active_lesson")
            else:
                self.connection.execute("UPDATE memory SET status='disabled',reason=? WHERE id=?", (reason, identifier))
                result = self._audit(identifier, "disabled", reason)
            self.connection.commit()
            return result
        except BaseException:
            self.connection.rollback()
            raise

    @staticmethod
    def _scope_rank(record: dict[str, Any], user: str, workflow: str) -> tuple[int, int, int]:
        protected_authority = AUTHORITY[record["source"]] if record["kind"] == "procedure" else 0
        return (protected_authority, int(record["user_id"] == user), int(record["workflow"] == workflow))

    @staticmethod
    def _scope_reason(record: dict[str, Any], user: str, workflow: str) -> str | None:
        if record["user_id"] not in {user, "*"}:
            return "outside_user_scope"
        if record["workflow"] not in {workflow, "shared"}:
            return "outside_workflow_scope"
        return None

    def select(
        self, *, query: str, principal: dict[str, Any], workflow: str, now: int,
        token_limit: int, render: Callable[[str, list[dict[str, Any]]], str],
        count: Callable[[str], int], required_keys: Iterable[str] | None = None,
        hybrid_retriever: Any = None,
    ) -> dict[str, Any]:
        """Select authorized, valid records within a complete rendered budget."""
        user, _ = self._principal(principal)
        if not isinstance(query, str) or not isinstance(workflow, str) or not IDENTIFIER.fullmatch(workflow):
            raise ValueError("invalid query or workflow")
        if type(now) is not int or now < 0 or type(token_limit) is not int or token_limit < 0:
            raise ValueError("now and token_limit must be nonnegative integers")
        if isinstance(required_keys, str):
            raise ValueError("required_keys must be a collection, not one string")
        required = set(required_keys or [])
        if not all(isinstance(key, str) for key in required):
            raise ValueError("required_keys must contain strings")
        eligible, excluded = [], []
        for record in self.records():
            reason = self._scope_reason(record, user, workflow)
            if reason:
                pass
            elif record["status"] != "active":
                reason = record["status"]
            elif record["observed_at"] > now:
                reason = "future_dated"
            elif record["expires_at"] is not None and record["expires_at"] <= now:
                reason = "expired"
            if reason:
                excluded.append({"id": record["id"], "reason": reason})
            else:
                eligible.append(record)

        # Procedures preserve authority first. Other slots prefer narrower scope.
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for record in eligible:
            slot = (record["kind"], record["key"])
            previous = grouped.get(slot)
            if previous is None:
                grouped[slot] = record
            elif self._scope_rank(record, user, workflow) > self._scope_rank(previous, user, workflow):
                excluded.append({"id": previous["id"], "reason": "shadowed_by_specific_scope"})
                grouped[slot] = record
            else:
                excluded.append({"id": record["id"], "reason": "shadowed_by_specific_scope"})
        eligible = list(grouped.values())
        missing = sorted(required - {record["key"] for record in eligible})
        mandatory = [r for r in eligible if r["pinned"] or r["key"] in required]
        mandatory.sort(key=lambda r: (r["kind"] != "procedure", r["kind"] != "preference", r["id"]))
        mandatory_ids = {r["id"] for r in mandatory}
        selected = list(mandatory)

        def measured(records: list[dict[str, Any]]) -> tuple[str, int]:
            prompt = render(query, records)
            if not isinstance(prompt, str):
                raise ValueError("render must return a string")
            tokens = count(prompt)
            if type(tokens) is not int or tokens < 0:
                raise ValueError("count must return a nonnegative integer")
            return prompt, tokens

        prompt, tokens = measured(selected)
        status = "ready"
        if tokens > token_limit:
            status = "blocked_budget"
        elif missing:
            status = "insufficient_evidence"
        query_terms = _terms(query)
        ranked = []
        optional = [record for record in eligible if record["id"] not in mandatory_ids]
        retrieval = {"mode": "lexical_overlap", "semantic_status": "not_configured"}
        if hybrid_retriever is not None and status == "ready" and optional:
            retrieval = hybrid_retriever.rank(query, optional, principal, workflow)
            available = {record["id"]: record for record in optional}
            seen = set()
            for item in retrieval["ranked"]:
                identifier = item["id"]
                if identifier not in available or identifier in seen:
                    raise ValueError("Retriever returned an unauthorized or duplicate record ID")
                seen.add(identifier)
                ranked.append((item["score"], available[identifier]))
            excluded.extend({"id": record["id"], "reason": "not_relevant"}
                for record in optional if record["id"] not in seen)
        else:
            if hybrid_retriever is not None:
                retrieval = {"mode": "not_run", "semantic_status": "mandatory_gate_or_no_optional_records"}
            for record in optional:
                overlap = len(query_terms & _terms(record["value"] + " " + record["key"]))
                if not overlap:
                    excluded.append({"id": record["id"], "reason": "not_relevant"})
                else:
                    ranked.append((overlap, record))
            ranked.sort(key=lambda pair: (-pair[0], -pair[1]["observed_at"], pair[1]["id"]))
        for overlap, record in ranked:
            if status != "ready":
                excluded.append({"id": record["id"], "reason": "request_" + status})
                continue
            trial_prompt, trial_tokens = measured(selected + [record])
            if trial_tokens > token_limit:
                excluded.append({"id": record["id"], "reason": "budget", "relevance": overlap})
            else:
                selected.append(record)
                prompt, tokens = trial_prompt, trial_tokens
        return {
            "status": status, "selected": selected, "excluded": excluded,
            "prompt": prompt, "token_count": tokens, "token_limit": token_limit,
            "missing_required_keys": missing, "retrieval": retrieval["mode"],
            "retrieval_details": retrieval,
        }

    def save_checkpoint(self, thread_id: str, state: Any, principal: dict[str, Any]) -> dict[str, Any]:
        user, _ = self._principal(principal)
        if not isinstance(thread_id, str) or not IDENTIFIER.fullmatch(thread_id):
            raise ValueError("invalid thread_id")
        serialized = json.dumps(state, ensure_ascii=False, allow_nan=False)
        with self.connection:
            revision = self.connection.execute("SELECT COALESCE(MAX(sequence),0) FROM audit_events").fetchone()[0]
            self.connection.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?) ON CONFLICT(user_id,thread_id) DO UPDATE SET state=excluded.state,memory_revision=excluded.memory_revision",
                (user, thread_id, serialized, revision),
            )
        return {"user_id": user, "thread_id": thread_id, "state": json.loads(serialized), "memory_revision": revision}

    def load_checkpoint(self, thread_id: str, principal: dict[str, Any]) -> Any:
        user, _ = self._principal(principal)
        row = self.connection.execute("SELECT state FROM checkpoints WHERE user_id=? AND thread_id=?", (user, thread_id)).fetchone()
        return json.loads(row["state"]) if row else None
