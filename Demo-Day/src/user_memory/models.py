import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def valid_id(value: str) -> str:
    # Reject ambiguous IDs instead of normalizing different IDs to the same namespace.
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,119}", value):
        raise ValueError("Identifiers must contain 1-120 letters, digits, dots, underscores, or hyphens.")
    if value == "_shared":
        raise ValueError("The shared namespace identifier is reserved.")
    return value


@dataclass(frozen=True)
class AppContext:
    org_id: str
    user_id: str
    is_admin: bool = False

    def __post_init__(self):
        valid_id(self.org_id)
        valid_id(self.user_id)

    def namespace(self, kind: str, *, shared: bool = False) -> tuple[str, ...]:
        return (self.org_id, "_shared" if shared else self.user_id, kind)


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssistantReply(Schema):
    reply: str
    update_global_policy: bool = False


class SectionPatch(Schema):
    summary: str = ""
    should_update: bool = False


class UserPatch(Schema):
    workContext: SectionPatch = Field(default_factory=SectionPatch)
    personalContext: SectionPatch = Field(default_factory=SectionPatch)
    topOfMind: SectionPatch = Field(default_factory=SectionPatch)


class HistoryPatch(Schema):
    recentMonths: SectionPatch = Field(default_factory=SectionPatch)
    earlierContext: SectionPatch = Field(default_factory=SectionPatch)
    longTermBackground: SectionPatch = Field(default_factory=SectionPatch)


class FactProposal(Schema):
    content: str
    category: Literal[
        "preference",
        "knowledge",
        "context",
        "behavior",
        "goal",
        "correction",
        "policy",
        "compliance",
        "legal",
        "disclaimer",
        "org_naming",
    ] = "context"
    confidence: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)
    evidence_span: str = ""
    supersedes_fact_ids: list[str] = Field(default_factory=list)


class MemoryUpdate(Schema):
    user: UserPatch = Field(default_factory=UserPatch)
    history: HistoryPatch = Field(default_factory=HistoryPatch)
    new_facts: list[FactProposal] = Field(default_factory=list)
    facts_to_remove: list[str] = Field(default_factory=list)
