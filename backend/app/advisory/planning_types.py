"""Versioned planning contracts; amounts derived from many goals have no input-size cap."""
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, Field

from app.advisory.state import GoalSnapshot, PlanningState
from app.advisory.types import AgentResult, OrchestratorDecision

Category = Literal['conservative', 'moderate', 'aggressive']
Readiness = Literal['ready_to_consider', 'deferred', 'insufficient_information']


class GoalRequirement(BaseModel):
    goal: GoalSnapshot
    remaining_amount: Decimal
    approximate_months: int | None
    required_monthly: Decimal | None
    status: Literal['future', 'completed', 'overdue']


class BudgetFacts(BaseModel):
    kind: Literal['budget'] = 'budget'
    capacity: Decimal | None


class DebtFacts(BaseModel):
    kind: Literal['debt'] = 'debt'
    review_required: bool
    reason_code: str | None


class EmergencyFacts(BaseModel):
    kind: Literal['emergency'] = 'emergency'
    gap: Decimal | None
    coverage: Decimal | None


class GoalFacts(BaseModel):
    kind: Literal['goal'] = 'goal'
    requirements: list[GoalRequirement]


class RiskFacts(BaseModel):
    kind: Literal['risk'] = 'risk'
    category: Category | None
    factor_codes: list[str]


class InvestmentFacts(BaseModel):
    kind: Literal['investment'] = 'investment'
    status: Readiness
    category: Category | None
    factor_codes: list[str]
    reasons: list[str]


class PlanningAgentResult(AgentResult):
    facts: Annotated[BudgetFacts | DebtFacts | EmergencyFacts | GoalFacts | RiskFacts | InvestmentFacts, Field(discriminator='kind')]


class EvidenceRef(BaseModel):
    agent_id: str
    finding_code: str


class NextAction(BaseModel):
    view: Literal['profile', 'goals', 'advisor']
    field: str | None = None
    goal_id: int | None = None


class PlanAction(BaseModel):
    code: str
    title: str
    reason: str
    source_refs: list[EvidenceRef]
    limitations: list[str] = []
    next_action: NextAction


class GoalAllocation(BaseModel):
    requirement: GoalRequirement
    allocated_monthly: Decimal | None
    funding_gap: Decimal | None
    status: Literal['completed', 'overdue', 'budget_covered', 'underfunded', 'missing_budget']
    source_refs: list[EvidenceRef]


class MonthlyPlan(BaseModel):
    capacity: Decimal | None
    emergency_allocation: Decimal | None
    goal_allocations: list[GoalAllocation]
    unassigned: Decimal | None
    hold_reason: str | None


class InvestmentAssessment(BaseModel):
    status: Readiness
    category: Category | None
    reasons: list[str]
    source_refs: list[EvidenceRef]


class PlanSummary(BaseModel):
    title: str
    text: str
    next_action: NextAction


class CoordinatedAdvice(BaseModel):
    summary: PlanSummary
    monthly_plan: MonthlyPlan
    investment: InvestmentAssessment
    priority_actions: list[PlanAction]


class AdvisoryResultV2(BaseModel):
    state: PlanningState
    decision: OrchestratorDecision
    agent_results: list[PlanningAgentResult]
    advice: CoordinatedAdvice
