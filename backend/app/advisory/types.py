from decimal import Decimal
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_serializer

from app.advisory.state import FinancialState


class Evidence(BaseModel):
    label: str
    value: Decimal | None
    unit: str


class Finding(BaseModel):
    code: str
    title: str
    reason: str
    priority: bool
    evidence: list[Evidence]
    limitations: list[str]
    impact: str | None = None
    suggested_action: str | None = None

    @model_serializer(mode="wrap")
    def serialize(self, handler):
        payload = handler(self)
        for key in ("impact", "suggested_action"):
            if payload.get(key) is None:
                payload.pop(key, None)
        return payload


class AgentResult(BaseModel):
    agent_id: str
    status: Literal["ok", "limited"]
    findings: list[Finding]
    limitations: list[str]


class AgentSelection(BaseModel):
    agent_id: str
    selected: bool
    reason: str


class OrchestratorDecision(BaseModel):
    method: Literal["rule_based", "random", "rl"] = "rule_based"
    rule_version: str
    selections: list[AgentSelection]


class PriorityAction(BaseModel):
    code: str
    title: str
    reason: str
    agent_id: str
    finding_code: str
    evidence: list[Evidence]
    limitations: list[str]


class AdvisoryResult(BaseModel):
    state: FinancialState
    decision: OrchestratorDecision
    agent_results: list[AgentResult]
    priority_actions: list[PriorityAction]
